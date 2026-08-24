"""
Agent Runtime
=============
Per-agent LLM call pipeline. One AgentRuntime instance per persona.

Pipeline per invocation:
  1. Check cooldown (skip if too soon)
  2. Load persona config (YAML)
  3. Build context (ContextBuilder)
  4. Call LLM (google-genai async)
  5. Parse response (ResponseParser)
  6. Handle tool call if present (ToolRegistry)
  7. Save message to SessionMemory
  8. Optionally trigger memory consolidation if buffer is full

All five agent personas share the same AgentRuntime class —
they differ only in their YAML config (model, tools, system prompt, cooldown).
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml
from google import genai
from google.genai import types as genai_types
from loguru import logger

from config.settings import settings
from core.models import AgentId, AgentMessage, EventType, ToolResult
from core.exceptions import AgentCooldownError, AgentRuntimeError
from agents.context_builder import ContextBuilder
from agents.response_parser import response_parser
from memory.short_term import SessionMemory
from memory.summarizer import memory_summarizer
from tools.registry import tool_registry
from tools.base_tool import ToolContext


# Directory containing persona YAML files
PERSONAS_DIR = Path(__file__).parent / "personas"


class AgentRuntime:
    """
    Single agent's full execution pipeline.
    Instantiate once per persona, reuse across the session.
    """

    def __init__(self, agent_id: AgentId):
        self.agent_id = agent_id
        self._config: Optional[dict] = None
        self._session: SessionMemory = SessionMemory(agent_id)
        self._context_builder = ContextBuilder()
        self._last_invocation: float = 0.0
        self._client: Optional[genai.Client] = None
        self._initialized = False

    # ------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Load persona config and initialize LLM client. Call once at startup."""
        if self._initialized:
            return

        # Load YAML config
        config_path = PERSONAS_DIR / f"{self.agent_id.value}.yaml"
        if not config_path.exists():
            raise AgentRuntimeError(
                f"Persona config not found: {config_path}"
            )

        with open(config_path, "r", encoding="utf-8") as f:
            self._config = yaml.safe_load(f)

        # Initialize Gemini client
        api_key = settings.resolved_api_key
        if not api_key:
            raise AgentRuntimeError(
                "No API key found. Set GEMINI_API_KEY or GOOGLE_API_KEY in your .env file."
            )

        self._client = genai.Client(api_key=api_key)
        self._initialized = True

        logger.info(
            f"AgentRuntime initialized: {self.agent_id.value} | "
            f"model={self._config.get('model')} | "
            f"cooldown={self._config.get('cooldown_seconds')}s"
        )

    # ------------------------------------------------------------------
    # MAIN INVOKE METHOD
    # ------------------------------------------------------------------

    async def invoke(
        self,
        user_message: str,
        triggered_by: EventType = EventType.USER_DIRECT_MESSAGE,
        memory_query: Optional[str] = None,
        memory_tags: Optional[list[str]] = None,
        bypass_cooldown: bool = False,
    ) -> AgentMessage:
        """
        Full pipeline: context → LLM → parse → optional tool → memory.
        Returns an AgentMessage.
        """
        if not self._initialized:
            await self.initialize()

        # 1. Cooldown check
        if not bypass_cooldown and not self._check_cooldown():
            cooldown = self._config.get("cooldown_seconds", 1200)
            raise AgentCooldownError(self.agent_id.value, cooldown)

        # 2. Build context packet
        try:
            context_text, context_debug = await self._context_builder.build(
                agent_id=self.agent_id,
                user_message=user_message,
                session=self._session,
                memory_query=memory_query,
                memory_tags=memory_tags,
            )
        except Exception as e:
            logger.warning(f"AgentRuntime[{self.agent_id.value}]: Context build partial failure: {e}")
            context_text = f"--- USER MESSAGE ---\n{user_message}"
            context_debug = {"memory_count": 0, "retrieved_memories": []}

        # 3. LLM call
        latency_ms = 0
        start_time = time.perf_counter()
        try:
            raw_response, in_tokens, out_tokens, tot_tokens, model_used = await self._call_llm(context_text)
            latency_ms += int((time.perf_counter() - start_time) * 1000)
            input_tokens = in_tokens
            output_tokens = out_tokens
            tokens_used = tot_tokens
        except Exception as e:
            raise AgentRuntimeError(
                f"LLM call failed for {self.agent_id.value}: {e}"
            ) from e

        # 4. Parse response
        parsed = response_parser.parse(raw_response, self.agent_id.value)

        # 5. Handle tool call if requested
        if parsed.has_tool_call and parsed.tool_name:
            tool_result = await self._execute_tool(parsed.tool_name, parsed.tool_args or {})
            # Re-invoke with tool result injected (one round-trip max)
            tool_context_text = (
                f"{context_text}\n\n"
                f"--- TOOL RESULT ({parsed.tool_name}) ---\n"
                f"{tool_result.data if tool_result.success else tool_result.error}"
            )
            try:
                followup_start = time.perf_counter()
                raw_response, followup_in, followup_out, followup_tot, _ = await self._call_llm(tool_context_text)
                input_tokens += followup_in
                output_tokens += followup_out
                tokens_used += followup_tot
                latency_ms += int((time.perf_counter() - followup_start) * 1000)
                parsed = response_parser.parse(raw_response, self.agent_id.value)
            except Exception as e:
                logger.error(f"Tool follow-up LLM call failed: {e}")

        # 6. Build final message
        import json
        message = AgentMessage(
            agent_id=self.agent_id,
            content=parsed.content,
            triggered_by=triggered_by,
            tokens_used=tokens_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model_used=model_used,
            latency_ms=latency_ms,
            tool_used=parsed.tool_name if parsed.has_tool_call else None,
            debug={
                "prompt_size": len(context_text),
                "memory_count": context_debug.get("memory_count", 0),
                "retrieved_memories": context_debug.get("retrieved_memories", []),
                "execution_time_ms": latency_ms
            }
        )

        # Save to SQLite database for auditing and history
        try:
            from data.database import db
            await db.execute_write(
                """
                INSERT INTO agent_messages (
                    id, agent_id, content, triggered_by, call_priority, tokens_used, input_tokens, output_tokens, model_used, debug, latency_ms, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    message.id,
                    message.agent_id.value,
                    message.content,
                    message.triggered_by.value if message.triggered_by else None,
                    message.call_priority.value,
                    message.tokens_used,
                    message.input_tokens,
                    message.output_tokens,
                    message.model_used,
                    json.dumps(message.debug),
                    message.latency_ms,
                )
            )
            logger.debug(f"AgentRuntime[{self.agent_id.value}]: Saved message to database.")
        except Exception as e:
            logger.warning(f"Failed to save agent message to database: {e}")

        # 7. Save to session memory
        self._session.add(message)
        self._last_invocation = time.time()

        # 8. Consolidate if buffer is full
        if self._session.is_full():
            logger.info(f"AgentRuntime[{self.agent_id.value}]: Session buffer full — consolidating.")
            try:
                await memory_summarizer.consolidate_session(
                    self._session, self._client
                )
            except Exception as e:
                logger.warning(f"Memory consolidation failed: {e}")

        logger.info(
            f"AgentRuntime[{self.agent_id.value}]: Response ready "
            f"({len(parsed.content)} chars, tokens_used={tokens_used}, latency_ms={latency_ms}, "
            f"triggered_by={triggered_by.value})"
        )

        return message

    # ------------------------------------------------------------------
    # LLM CALL
    # ------------------------------------------------------------------

    async def _call_llm(self, context: str) -> tuple[str, int, int, int, str]:
        """Make the async Gemini API call. Returns (text, input_tokens, output_tokens, total_tokens, model)."""
        model = self._config.get("model", "gemini-2.5-flash-preview-05-20")
        system_prompt = self._config.get("system_prompt", "")
        temperature = float(self._config.get("temperature", 1.0))
        max_tokens = int(self._config.get("max_output_tokens", 400))

        response = await self._client.aio.models.generate_content(
            model=model,
            contents=context,
            config=genai_types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        )

        in_tokens = 0
        out_tokens = 0
        tot_tokens = 0
        if response.usage_metadata:
            in_tokens = response.usage_metadata.prompt_token_count or 0
            out_tokens = response.usage_metadata.candidates_token_count or 0
            tot_tokens = response.usage_metadata.total_token_count or 0

        return response.text or "", in_tokens, out_tokens, tot_tokens, model

    # ------------------------------------------------------------------
    # TOOL EXECUTION
    # ------------------------------------------------------------------

    async def _execute_tool(self, tool_name: str, args: dict) -> ToolResult:
        """Execute a tool call from the agent."""
        ctx = ToolContext(
            agent_id=self.agent_id.value,
            trace_id=f"{self.agent_id.value}-tool",
        )
        result = await tool_registry.execute(tool_name, args, ctx)
        logger.debug(
            f"AgentRuntime[{self.agent_id.value}]: Tool '{tool_name}' "
            f"→ success={result.success}"
        )
        return result

    # ------------------------------------------------------------------
    # COOLDOWN CHECK
    # ------------------------------------------------------------------

    def _check_cooldown(self) -> bool:
        """Returns True if the agent is allowed to speak (cooldown elapsed)."""
        cooldown = self._config.get("cooldown_seconds", 1200)
        elapsed = time.time() - self._last_invocation
        return elapsed >= cooldown

    def time_until_ready(self) -> int:
        """Seconds until this agent can speak again (0 if ready)."""
        cooldown = self._config.get("cooldown_seconds", 1200) if self._config else 1200
        elapsed = time.time() - self._last_invocation
        return max(0, int(cooldown - elapsed))

    # ------------------------------------------------------------------
    # SESSION MANAGEMENT
    # ------------------------------------------------------------------

    def get_session(self) -> SessionMemory:
        return self._session

    async def end_session(self) -> None:
        """Consolidate and clear the session. Call at end of day."""
        if self._initialized and self._client:
            await memory_summarizer.consolidate_session(self._session, self._client)
        self._session.clear()

    def is_ready(self) -> bool:
        """True if initialized and cooldown has passed."""
        return self._initialized and self._check_cooldown()

    @property
    def display_name(self) -> str:
        return self._config.get("display_name", self.agent_id.value) if self._config else self.agent_id.value
