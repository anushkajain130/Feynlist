"""
Agents Router
=============
All agent interaction endpoints + real-time WebSocket.

POST /api/agents/message          — send a message, get response
GET  /api/agents/status           — cooldown state for all agents
GET  /api/agents/{agent_id}/ask   — ask one specific agent directly
WS   /api/agents/ws               — real-time agent response stream
"""

from __future__ import annotations

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from loguru import logger

from api.schemas import (
    SendMessageRequest, AgentMessageResponse,
    CouncilResponse, AgentStatusResponse,
)
from agents.orchestrator import orchestrator
from core.models import AgentId, AppEvent, EventType
from core.exceptions import AgentCooldownError, AgentRuntimeError, AgentUnavailableError


def _cooldown_message(agent_id: str, seconds: int) -> str:
    minutes = max(1, round(seconds / 60))
    return f"{agent_id.capitalize()} is taking a short break. Try again in about {minutes} min."


def _unavailable_detail(e: AgentRuntimeError) -> str:
    """User-safe text for any agent failure; never the raw provider error."""
    if isinstance(e, AgentUnavailableError):
        return e.user_message
    return AgentUnavailableError("provider_error").user_message
from notifications.triggers import emit_user_message

router = APIRouter(prefix="/api/agents", tags=["Agents"])


def _agent_msg_to_response(msg) -> AgentMessageResponse:
    # If debug is a JSON string, deserialize it
    debug_val = None
    if msg.debug:
        if isinstance(msg.debug, str):
            try:
                debug_val = json.loads(msg.debug)
            except Exception:
                debug_val = {"raw": msg.debug}
        elif isinstance(msg.debug, dict):
            debug_val = msg.debug

    return AgentMessageResponse(
        id=msg.id,
        agent_id=msg.agent_id.value,
        display_name=orchestrator.get_runtime(msg.agent_id).display_name,
        content=msg.content,
        timestamp=msg.timestamp.isoformat() if hasattr(msg.timestamp, "isoformat") else str(msg.timestamp),
        triggered_by=msg.triggered_by.value if (msg.triggered_by and hasattr(msg.triggered_by, "value")) else msg.triggered_by,
        tool_used=msg.tool_used,
        input_tokens=getattr(msg, "input_tokens", 0),
        output_tokens=getattr(msg, "output_tokens", 0),
        tokens_used=getattr(msg, "tokens_used", 0),
        model_used=getattr(msg, "model_used", ""),
        latency_ms=getattr(msg, "latency_ms", 0),
        debug=debug_val,
    )


@router.post("/message", response_model=CouncilResponse)
async def send_message(req: SendMessageRequest):
    """
    Send a user message and receive agent response(s).
    - No agent_id → orchestrator picks the right agent (or council)
    - With agent_id → that specific agent responds
    """
    # Detect council call vs single agent
    is_council_call = any(
        t in req.message.lower()
        for t in ["hi council", "@council", "hey council"]
    )

    if req.agent_id and not is_council_call:
        # Direct to specific agent
        try:
            agent_id = AgentId(req.agent_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown agent: '{req.agent_id}'. "
                       f"Valid: {[a.value for a in AgentId]}"
            )
        try:
            msg = await orchestrator.ask_agent(
                agent_id=agent_id,
                message=req.message,
                bypass_cooldown=req.bypass_cooldown,
            )
            return CouncilResponse(
                messages=[_agent_msg_to_response(msg)],
                total_agents=1,
            )
        except AgentCooldownError as e:
            raise HTTPException(status_code=429, detail=_cooldown_message(e.agent_id, e.seconds_remaining))
        except AgentRuntimeError as e:
            raise HTTPException(status_code=503, detail=_unavailable_detail(e))

    else:
        # Route via event bus → orchestrator
        event = AppEvent(
            event_type=EventType.USER_DIRECT_MESSAGE,
            source="user",
            payload={"message": req.message},
        )
        try:
            messages = await orchestrator.dispatch(event, raise_unavailable=True)
        except AgentRuntimeError as e:
            raise HTTPException(status_code=503, detail=_unavailable_detail(e))

        if not messages:
            raise HTTPException(
                status_code=429,
                detail="The Council is taking a short break. Try again in a few minutes."
            )

        return CouncilResponse(
            messages=[_agent_msg_to_response(m) for m in messages],
            total_agents=len(messages),
        )


@router.get("/status", response_model=AgentStatusResponse)
async def get_agent_status():
    """Return cooldown state for all 5 agents."""
    from config.settings import settings
    return AgentStatusResponse(
        agents=orchestrator.agent_status(),
        ai_configured=settings.has_api_key,
    )


@router.get("/{agent_id}/ask", response_model=AgentMessageResponse)
async def ask_agent(agent_id: str, message: str, bypass_cooldown: bool = False):
    """Ask one specific agent a question (GET with query param)."""
    try:
        agent = AgentId(agent_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown agent: '{agent_id}'")

    try:
        msg = await orchestrator.ask_agent(
            agent_id=agent,
            message=message,
            bypass_cooldown=bypass_cooldown,
        )
        return _agent_msg_to_response(msg)
    except AgentCooldownError as e:
        raise HTTPException(status_code=429, detail=_cooldown_message(e.agent_id, e.seconds_remaining))
    except AgentRuntimeError as e:
        raise HTTPException(status_code=503, detail=_unavailable_detail(e))


# =============================================================================
# WEBSOCKET — Real-Time Agent Stream
# =============================================================================

class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.active.append(ws)
        logger.info(f"WS: client connected ({len(self.active)} total)")

    def disconnect(self, ws: WebSocket) -> None:
        self.active.remove(ws)
        logger.info(f"WS: client disconnected ({len(self.active)} remaining)")

    async def broadcast(self, data: dict) -> None:
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active.remove(ws)

    async def send_to(self, ws: WebSocket, data: dict) -> None:
        await ws.send_json(data)


ws_manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Real-time bidirectional WebSocket.

    Client sends:  {"message": "...", "agent_id": "freya"}
    Server sends:  {"type": "agent_message", "agent_id": "freya", "content": "..."}
                   {"type": "status", "message": "..."}
                   {"type": "error", "message": "..."}
    """
    await ws_manager.connect(websocket)

    try:
        # Send initial connection confirmation
        await ws_manager.send_to(websocket, {
            "type": "status",
            "message": "Connected to Feynlist Council.",
        })

        while True:
            raw = await websocket.receive_text()

            try:
                data = json.loads(raw)
                user_message = data.get("message", "")
                agent_id_str = data.get("agent_id")

                if not user_message:
                    await ws_manager.send_to(websocket, {
                        "type": "error",
                        "message": "Empty message received."
                    })
                    continue

                # Notify client: processing started
                await ws_manager.send_to(websocket, {
                    "type": "status",
                    "message": "Thinking..."
                })

                # Build event and dispatch
                event = AppEvent(
                    event_type=EventType.USER_DIRECT_MESSAGE,
                    source="user",
                    payload={
                        "message": user_message,
                        "agent_id": agent_id_str,
                    },
                )

                if agent_id_str and agent_id_str != "council":
                    try:
                        agent_id = AgentId(agent_id_str)
                        messages = [await orchestrator.ask_agent(
                            agent_id=agent_id,
                            message=user_message,
                            bypass_cooldown=True,
                        )]
                    except AgentCooldownError as e:
                        messages = []
                        await ws_manager.send_to(websocket, {
                            "type": "error",
                            "message": _cooldown_message(e.agent_id, e.seconds_remaining),
                        })
                    except AgentRuntimeError as e:
                        messages = []
                        await ws_manager.send_to(websocket, {
                            "type": "error", "message": _unavailable_detail(e)
                        })
                else:
                    try:
                        messages = await orchestrator.dispatch(event, raise_unavailable=True)
                    except AgentRuntimeError as e:
                        messages = []
                        await ws_manager.send_to(websocket, {
                            "type": "error", "message": _unavailable_detail(e)
                        })
                    else:
                        if not messages:
                            await ws_manager.send_to(websocket, {
                                "type": "error",
                                "message": "The Council is taking a short break. Try again in a few minutes.",
                            })

                # Stream each agent response
                for msg in messages:
                    debug_val = None
                    if msg.debug:
                        if isinstance(msg.debug, str):
                            try:
                                debug_val = json.loads(msg.debug)
                            except Exception:
                                debug_val = {"raw": msg.debug}
                        elif isinstance(msg.debug, dict):
                            debug_val = msg.debug

                    await ws_manager.send_to(websocket, {
                        "type": "agent_message",
                        "id": msg.id,
                        "agent_id": msg.agent_id.value,
                        "display_name": orchestrator.get_runtime(msg.agent_id).display_name,
                        "content": msg.content,
                        "timestamp": msg.timestamp.isoformat() if hasattr(msg.timestamp, "isoformat") else str(msg.timestamp),
                        "tool_used": msg.tool_used,
                        "input_tokens": getattr(msg, "input_tokens", 0),
                        "output_tokens": getattr(msg, "output_tokens", 0),
                        "tokens_used": getattr(msg, "tokens_used", 0),
                        "model_used": getattr(msg, "model_used", ""),
                        "latency_ms": getattr(msg, "latency_ms", 0),
                        "debug": debug_val,
                    })
                    await asyncio.sleep(0.05)  # Slight delay between messages

            except json.JSONDecodeError:
                await ws_manager.send_to(websocket, {
                    "type": "error",
                    "message": "Invalid JSON received."
                })
            except Exception as e:
                logger.error(f"WS: error handling message: {e}")
                await ws_manager.send_to(websocket, {
                    "type": "error",
                    "message": "Internal error. Please try again."
                })

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@router.get("/tokens/today")
async def get_tokens_today():
    """Return total tokens consumed by all agents today."""
    from data.database import db
    from datetime import date
    try:
        # Get count of tokens used today from agent_messages
        # (matching current date prefix in timestamp column)
        today_str = date.today().isoformat()
        row = await db.fetch_one(
            "SELECT SUM(tokens_used) as t FROM agent_messages WHERE timestamp LIKE ?", 
            (f"{today_str}%",)
        )
        total = row["t"] if row and row["t"] else 0
        return {"total_tokens_today": total}
    except Exception as e:
        logger.warning(f"Failed to fetch today's token usage: {e}")
        return {"total_tokens_today": 0}
