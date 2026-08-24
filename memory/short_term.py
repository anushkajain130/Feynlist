"""
Short-Term Memory (Session Memory)
====================================
In-process deque of recent agent messages for the current session.
One SessionMemory instance per AgentRuntime.

Responsibilities:
  - Store last N agent messages (configurable, default 20)
  - Provide compressed conversation history for LLM context
  - Trigger consolidation to long-term memory when buffer is full
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Optional

from loguru import logger

from core.models import AgentMessage, AgentId


class SessionMemory:
    """
    In-process short-term memory for one agent.
    Thread-safe via asyncio (single-threaded event loop).
    """

    def __init__(self, agent_id: AgentId, max_size: int = 20):
        self.agent_id = agent_id
        self.max_size = max_size
        self._buffer: deque[AgentMessage] = deque(maxlen=max_size)
        self._session_start = datetime.now()

    # ------------------------------------------------------------------
    # WRITE
    # ------------------------------------------------------------------

    def add(self, message: AgentMessage) -> None:
        """Add a new agent message. Oldest message is dropped if full."""
        self._buffer.append(message)
        logger.debug(
            f"SessionMemory[{self.agent_id.value}] +message "
            f"(buffer={len(self._buffer)}/{self.max_size})"
        )

    def clear(self) -> None:
        """Clear the session buffer (call at end of day or session end)."""
        self._buffer.clear()
        logger.info(f"SessionMemory[{self.agent_id.value}] cleared.")

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    def get_recent(self, n: int = 5) -> list[AgentMessage]:
        """Get the N most recent messages."""
        messages = list(self._buffer)
        return messages[-n:]

    def get_all(self) -> list[AgentMessage]:
        """Get all messages in the buffer."""
        return list(self._buffer)

    def is_full(self) -> bool:
        return len(self._buffer) >= self.max_size

    def size(self) -> int:
        return len(self._buffer)

    # ------------------------------------------------------------------
    # CONTEXT FORMATTING
    # ------------------------------------------------------------------

    def format_for_prompt(self, n: int = 5, max_chars_per_msg: int = 300) -> str:
        """
        Format the last N messages as a compact string for LLM context.
        Truncates long messages to save tokens.

        Returns:
            A formatted string like:
            [14:23] Freya: You just missed your Differential Equations block...
            [14:35] Freya: Good — you started the next one on time.
        """
        recent = self.get_recent(n)
        if not recent:
            return "(No recent conversation)"

        lines = []
        for msg in recent:
            time_str = msg.timestamp.strftime("%H:%M")
            content = msg.content
            if len(content) > max_chars_per_msg:
                content = content[:max_chars_per_msg] + "..."
            lines.append(f"[{time_str}] {msg.agent_id.value.capitalize()}: {content}")

        return "\n".join(lines)

    def to_consolidation_text(self) -> str:
        """
        Returns all buffered messages as text for long-term memory consolidation.
        Used by the summarizer to compress the session into a memory entry.
        """
        all_msgs = self.get_all()
        if not all_msgs:
            return ""

        session_date = self._session_start.strftime("%Y-%m-%d")
        lines = [f"Session on {session_date}:"]
        for msg in all_msgs:
            time_str = msg.timestamp.strftime("%H:%M")
            lines.append(f"  [{time_str}] {msg.agent_id.value}: {msg.content[:200]}")

        return "\n".join(lines)
