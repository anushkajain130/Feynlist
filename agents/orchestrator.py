"""
Agent Orchestrator
==================
Routes events to the appropriate agents and manages the Council's response flow.

Responsibilities:
  - Decide WHICH agent(s) should respond to each event
  - Enforce global cooldown (no agent spam)
  - Support both single-agent and full-Council response modes
  - Queue responses sequentially (Council mode) or fire the right one immediately

Two modes:
  SOLO: One specific agent responds (e.g., Freya for task_missed)
  COUNCIL: All agents respond in sequence (e.g., user says "hi council")
"""

from __future__ import annotations

from collections import OrderedDict

import asyncio
import time
from typing import Optional

from loguru import logger

from config.settings import settings
from core.models import AgentId, AgentMessage, AppEvent, EventType
from core.exceptions import AgentCooldownError, AgentRuntimeError, AgentUnavailableError
from agents.runtime import AgentRuntime


# Maps event types → which agent responds (SOLO mode). Only events that some
# code path actually emits are listed (checked by tests/unit/test_triggers.py).
# Async callbacks(messages) told about every proactive message (e.g. the websocket
# manager pushes them to the session's open Council page).
PROACTIVE_LISTENERS: list = []

EVENT_AGENT_MAP: dict[EventType, AgentId] = {
    EventType.TASK_MISSED:           AgentId.FREYA,
    EventType.DAY_START:             AgentId.FREYA,
    EventType.TASK_COMPLETED:        AgentId.ALBEDO,
    EventType.STREAK_MILESTONE:      AgentId.ALBEDO,
    EventType.BURNOUT_DETECTED:      AgentId.ANYA,
    EventType.STREAK_BROKEN:         AgentId.ANYA,
    EventType.DAY_END_REVIEW:        AgentId.ANYA,
    EventType.SCHEDULED_CHECKIN:     AgentId.ZEROTWO,
    EventType.USER_DIRECT_MESSAGE:   AgentId.FREYA,  # Default; overridden by @mention
}

# Council order for COUNCIL mode (who speaks first, second, etc.)
COUNCIL_ORDER = [
    AgentId.FREYA,
    AgentId.ALBEDO,
    AgentId.ANYA,
    AgentId.ZEROTWO,
    AgentId.MOHINI,
]


class Orchestrator:
    """
    Routes events to agents and manages response flow.
    Maintains one AgentRuntime per persona.
    """

    def __init__(self):
        self._runtimes: dict[AgentId, AgentRuntime] = {
            agent_id: AgentRuntime(agent_id)
            for agent_id in AgentId
        }
        self._global_cooldown_until: float = 0.0
        self._initialized = False

    # ------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize all agent runtimes. Call once at startup."""
        if self._initialized:
            return

        logger.info("Orchestrator: initializing all agent runtimes...")
        init_tasks = [rt.initialize() for rt in self._runtimes.values()]

        results = await asyncio.gather(*init_tasks, return_exceptions=True)
        failed = [
            (list(self._runtimes.keys())[i], e)
            for i, e in enumerate(results)
            if isinstance(e, Exception)
        ]

        if failed:
            for agent_id, err in failed:
                reason = getattr(err, "reason", None)
                hint = " (set GEMINI_API_KEY on the server)" if reason == "no_api_key" else ""
                logger.warning(f"Orchestrator: {agent_id.value} failed to init: {reason or err}{hint}")
            if len(failed) == len(self._runtimes):
                logger.error("Orchestrator: ALL agent runtimes failed to initialize.")
            else:
                logger.warning(f"Orchestrator: {len(failed)} runtime(s) failed, {len(self._runtimes) - len(failed)} ready.")

        self._initialized = True
        ready = sum(1 for rt in self._runtimes.values() if rt._initialized)
        logger.info(f"Orchestrator: {ready}/{len(self._runtimes)} runtimes ready.")

    # ------------------------------------------------------------------
    # DISPATCH (main entry point from EventBus)
    # ------------------------------------------------------------------

    async def dispatch(self, event: AppEvent, raise_unavailable: bool = False) -> list[AgentMessage]:
        """
        Handle an event. Returns list of AgentMessage responses.
        Routes to SOLO or COUNCIL mode based on event type.

        raise_unavailable: for user-initiated calls, re-raise AgentUnavailableError
        (no key / quota / provider error) so the caller can show a friendly message
        instead of silently returning nothing.
        """
        if not self._initialized:
            await self.initialize()

        from core.session import bypass_cooldowns
        is_chat = event.event_type == EventType.USER_DIRECT_MESSAGE

        # Global cooldown limits unprompted (proactive) messages only; a person
        # chatting is never blocked by it. Demo controls may bypass it.
        if not is_chat and not bypass_cooldowns.get() and not self._global_cooldown_ok():
            remaining = int(self._global_cooldown_until - time.time())
            logger.debug(f"Orchestrator: global cooldown, {remaining}s remaining.")
            return []

        # Detect @mentions in user message
        mentioned_agent = self._detect_mention(event)

        # COUNCIL mode: user addressed the full council
        if is_chat and self._is_council_call(event):
            return await self._invoke_council(event, raise_unavailable)

        # SOLO mode: pick one agent
        target_agent = mentioned_agent or EVENT_AGENT_MAP.get(event.event_type, AgentId.FREYA)
        messages = await self._invoke_solo(target_agent, event, raise_unavailable)
        if not is_chat and messages:
            await self._deliver_proactive(messages)
        return messages

    async def _deliver_proactive(self, messages: list[AgentMessage]) -> None:
        """Hand unprompted messages to the current request (demo) and to live listeners."""
        from core.session import proactive_sink
        sink = proactive_sink.get()
        if sink is not None:
            sink.extend(messages)
        for listener in list(PROACTIVE_LISTENERS):
            try:
                await listener(messages)
            except Exception as e:
                logger.warning(f"Orchestrator: proactive listener failed: {e}")

    # ------------------------------------------------------------------
    # SOLO INVOKE
    # ------------------------------------------------------------------

    async def _invoke_solo(
        self, agent_id: AgentId, event: AppEvent, raise_unavailable: bool = False
    ) -> list[AgentMessage]:
        """Invoke a single agent and return their message."""
        runtime = self._runtimes[agent_id]
        user_message = event.payload.get("message", "") if event.payload else ""

        from core.session import bypass_cooldowns
        try:
            message = await runtime.invoke(
                user_message=user_message,
                triggered_by=event.event_type,
                memory_query=user_message,
                bypass_cooldown=bypass_cooldowns.get(),
            )
            self._set_global_cooldown()
            return [message]
        except AgentCooldownError as e:
            logger.debug(f"Orchestrator: {agent_id.value} on cooldown — skipping.")
            return []
        except AgentUnavailableError as e:
            logger.warning(f"Orchestrator: {agent_id.value} unavailable ({e.reason}).")
            if raise_unavailable:
                raise
            return []
        except AgentRuntimeError as e:
            logger.error(f"Orchestrator: {agent_id.value} runtime error: {e}")
            if raise_unavailable:
                raise AgentUnavailableError("provider_error") from e
            return []

    # ------------------------------------------------------------------
    # COUNCIL INVOKE
    # ------------------------------------------------------------------

    async def _invoke_council(
        self, event: AppEvent, raise_unavailable: bool = False
    ) -> list[AgentMessage]:
        """
        Invoke all agents sequentially (Council mode).
        Each agent can see the responses of the previous agents in the session.
        """
        user_message = event.payload.get("message", "") if event.payload else ""
        responses = []
        last_unavailable: AgentUnavailableError | None = None

        for agent_id in COUNCIL_ORDER:
            runtime = self._runtimes[agent_id]

            # Skip agents that failed to initialise (e.g. no API key)
            if not runtime._initialized:
                try:
                    await runtime.initialize()
                except AgentUnavailableError as e:
                    last_unavailable = e
                    continue

            # Skip agents on individual cooldown (unless it's a direct message)
            if not runtime.is_ready():
                logger.debug(f"Orchestrator council: skipping {agent_id.value} (not ready)")
                continue

            try:
                message = await runtime.invoke(
                    user_message=user_message,
                    triggered_by=event.event_type,
                    bypass_cooldown=True,  # Council mode bypasses individual cooldowns
                )
                responses.append(message)

                # Small delay between agents — makes the response feel sequential
                await asyncio.sleep(0.1)

            except AgentUnavailableError as e:
                logger.warning(f"Orchestrator council: {agent_id.value} unavailable ({e.reason}).")
                last_unavailable = e
            except Exception as e:
                logger.error(f"Orchestrator council: {agent_id.value} failed: {e}")

        if responses:
            self._set_global_cooldown()
        elif raise_unavailable and last_unavailable is not None:
            raise last_unavailable
        return responses

    # ------------------------------------------------------------------
    # DIRECT AGENT ACCESS
    # ------------------------------------------------------------------

    async def ask_agent(
        self,
        agent_id: AgentId,
        message: str,
        bypass_cooldown: bool = False,
    ) -> AgentMessage:
        """
        Directly invoke a specific agent.
        Used by the GUI when the user talks to one agent explicitly.
        """
        if not self._initialized:
            await self.initialize()

        runtime = self._runtimes[agent_id]
        return await runtime.invoke(
            user_message=message,
            triggered_by=EventType.USER_DIRECT_MESSAGE,
            bypass_cooldown=bypass_cooldown,
        )

    def get_runtime(self, agent_id: AgentId) -> AgentRuntime:
        return self._runtimes[agent_id]

    # ------------------------------------------------------------------
    # STATUS
    # ------------------------------------------------------------------

    def agent_status(self) -> dict[str, dict]:
        """Returns ready state and cooldown remaining for each agent."""
        return {
            agent_id.value: {
                "ready": rt.is_ready(),
                "seconds_until_ready": rt.time_until_ready(),
            }
            for agent_id, rt in self._runtimes.items()
        }

    async def end_day(self) -> None:
        """Call at end of each day to consolidate all agent sessions."""
        logger.info("Orchestrator: running end-of-day consolidation.")
        for rt in self._runtimes.values():
            await rt.end_session()

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    def _global_cooldown_ok(self) -> bool:
        return time.time() >= self._global_cooldown_until

    def _set_global_cooldown(self) -> None:
        cooldown = settings.global_agent_cooldown_seconds
        self._global_cooldown_until = time.time() + cooldown

    @staticmethod
    def _detect_mention(event: AppEvent) -> Optional[AgentId]:
        """
        Check if the user's message @mentions a specific agent.
        e.g., "@freya what do you think?" → AgentId.FREYA
        """
        msg = (event.payload or {}).get("message", "").lower()
        mention_map = {
            "@freya": AgentId.FREYA,
            "@albedo": AgentId.ALBEDO,
            "@anya": AgentId.ANYA,
            "@zerotwo": AgentId.ZEROTWO,
            "@zero_two": AgentId.ZEROTWO,
            "@mohini": AgentId.MOHINI,
        }
        for mention, agent_id in mention_map.items():
            if mention in msg:
                return agent_id
        return None

    @staticmethod
    def _is_council_call(event: AppEvent) -> bool:
        """
        Returns True if the user is addressing the full Council.
        Triggered by: "hi council", "@council", or no specific @mention.
        """
        msg = (event.payload or {}).get("message", "").lower()
        council_triggers = ["hi council", "@council", "hey council", "what do you all"]
        return any(t in msg for t in council_triggers)


# ---------------------------------------------------------------------------
# Per-session orchestrators (demo mode)
# ---------------------------------------------------------------------------
# Each evaluator session gets its own runtimes, so chat memory and cooldowns
# never leak between people. Outside a session the default instance is used.

_default_orchestrator = Orchestrator()
_session_orchestrators: "OrderedDict[str, Orchestrator]" = OrderedDict()


def orchestrator_for_session(session_id: str | None) -> Orchestrator:
    if session_id is None:
        return _default_orchestrator
    orch = _session_orchestrators.get(session_id)
    if orch is None:
        orch = Orchestrator()
        _session_orchestrators[session_id] = orch
        while len(_session_orchestrators) > settings.demo_max_sessions:
            _session_orchestrators.popitem(last=False)
    else:
        _session_orchestrators.move_to_end(session_id)
    return orch


def drop_session_orchestrator(session_id: str) -> None:
    _session_orchestrators.pop(session_id, None)


class _OrchestratorProxy:
    """`orchestrator` used everywhere; resolves to the current session's instance."""

    def _target(self) -> Orchestrator:
        from core.session import current_session_id
        return orchestrator_for_session(current_session_id.get())

    def __getattr__(self, name):
        return getattr(self._target(), name)

    def __setattr__(self, name, value):
        setattr(self._target(), name, value)


orchestrator = _OrchestratorProxy()
