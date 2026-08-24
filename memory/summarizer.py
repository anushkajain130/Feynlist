"""
Memory Summarizer
=================
Compresses short-term session memory into long-term memory entries.

The summarizer is called:
  1. At end of each day (scheduled job)
  2. When short-term buffer is full (triggered by AgentRuntime)
  3. Manually via the CLI

It uses a cheap LLM call (Flash Lite) to summarize the session
into 2–3 key behavioral observations, which are stored as
long-term MemoryEntry records with appropriate tags and importance.

This is what makes the memory system sustainable at scale —
instead of growing unboundedly, sessions are compressed into
high-signal summary entries.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from loguru import logger

from core.models import AgentId, MemoryEntry, MemoryType
from data.repositories.memory_repo import memory_repo
from memory.short_term import SessionMemory


# Prompt template for the summarizer LLM call
SUMMARIZER_SYSTEM_PROMPT = """You are a behavioral analyst assistant.
You will be given a session transcript of an AI productivity coach talking to a user.
Extract 2–4 concise, factual observations about the user's behavior, patterns, or preferences.

Rules:
- Write each observation as one sentence.
- Focus on PATTERNS, not single events (unless the event is highly significant).
- Classify each with a type: behavioral, emotional, factual, preference, or productivity.
- Assign importance 0.0–1.0 (0.3=minor, 0.6=notable, 0.9=highly significant).
- Add relevant tags (2–4 keywords).

Output as JSON array:
[
  {
    "type": "behavioral",
    "content": "User tends to deviate from schedule around 14:00–15:00.",
    "importance": 0.7,
    "tags": ["deviation", "afternoon", "time-awareness"]
  }
]

Only output the JSON array. No other text."""


class MemorySummarizer:
    """
    Condenses SessionMemory into long-term MemoryEntry records.
    Uses a cheap LLM call to extract behavioral observations.
    """

    async def consolidate_session(
        self,
        session: SessionMemory,
        llm_client=None,  # google.genai.Client — injected to avoid circular import
        model: str = "gemini-2.5-flash-lite-preview-06-17",
    ) -> list[MemoryEntry]:
        """
        Summarize a session's short-term memory into long-term entries.

        Returns list of MemoryEntry objects that were saved.
        If LLM is unavailable, falls back to a rule-based extraction.
        """
        if session.size() == 0:
            logger.debug(f"MemorySummarizer: empty session for {session.agent_id}, skipping.")
            return []

        session_text = session.to_consolidation_text()

        # Try LLM-based extraction first
        if llm_client is not None:
            entries = await self._llm_extract(
                session_text, session.agent_id, llm_client, model
            )
        else:
            # Fallback: simple rule-based extraction
            entries = self._rule_based_extract(session_text, session.agent_id)

        if entries:
            await memory_repo.bulk_save(entries)
            logger.info(
                f"MemorySummarizer: saved {len(entries)} memories "
                f"from {session.agent_id.value} session"
            )

        return entries

    async def _llm_extract(
        self,
        session_text: str,
        agent_id: AgentId,
        llm_client,
        model: str,
    ) -> list[MemoryEntry]:
        """Extract memories using LLM summarization."""
        import json

        try:
            response = await llm_client.aio.models.generate_content(
                model=model,
                contents=session_text,
                config={"system_instruction": SUMMARIZER_SYSTEM_PROMPT},
            )
            raw = response.text.strip()

            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            observations = json.loads(raw)
            entries = []
            for obs in observations:
                entry = MemoryEntry(
                    agent_id=agent_id.value,
                    memory_type=MemoryType(obs.get("type", "factual")),
                    content=obs["content"],
                    tags=obs.get("tags", []),
                    importance=float(obs.get("importance", 0.5)),
                )
                entries.append(entry)
            return entries

        except Exception as e:
            logger.warning(
                f"MemorySummarizer: LLM extraction failed ({e}), "
                f"falling back to rule-based."
            )
            return self._rule_based_extract(session_text, agent_id)

    @staticmethod
    def _rule_based_extract(
        session_text: str, agent_id: AgentId
    ) -> list[MemoryEntry]:
        """
        Fallback: extract a single conversational memory entry
        without LLM, just preserving the session summary.
        """
        if not session_text:
            return []

        entry = MemoryEntry(
            agent_id=agent_id.value,
            memory_type=MemoryType.CONVERSATIONAL,
            content=session_text[:500],  # Truncate to 500 chars
            tags=["session-summary"],
            importance=0.3,
        )
        return [entry]

    async def run_daily_consolidation(
        self,
        sessions: list[SessionMemory],
        llm_client=None,
    ) -> int:
        """
        End-of-day job: consolidate all agent sessions.
        Returns total number of memory entries created.
        """
        total = 0
        for session in sessions:
            entries = await self.consolidate_session(session, llm_client)
            total += len(entries)
            session.clear()

        logger.info(f"MemorySummarizer: daily consolidation complete — {total} entries created.")
        return total


# Singleton
memory_summarizer = MemorySummarizer()
