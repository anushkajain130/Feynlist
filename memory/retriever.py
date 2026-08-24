"""
Memory Retriever
================
Retrieves the most relevant memories for an agent's LLM context call.

Ranking formula:
    score = w_recency * recency_score
          + w_importance * importance
          + w_relevance * relevance_score

Where:
    recency_score = exp(-days_since_access / decay_days)
    relevance_score = keyword overlap (V1); vector similarity (V2)

The retriever is called by context_builder.py before every LLM call.
It returns a compressed, ranked list of memories within a token budget.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from loguru import logger

from core.models import MemoryEntry
from data.repositories.memory_repo import memory_repo


class MemoryRetriever:
    """
    Retrieves and ranks memories for agent context assembly.

    Default weights:
        recency:    0.35  (recently accessed memories are more relevant)
        importance: 0.40  (user-set or agent-set importance)
        relevance:  0.25  (keyword match against query)

    Decay:
        recency_score = exp(-days_since_access / decay_days)
        decay_days=14 means memories not accessed in 2 weeks score near 0.
    """

    def __init__(
        self,
        recency_weight: float = 0.35,
        importance_weight: float = 0.40,
        relevance_weight: float = 0.25,
        decay_days: float = 14.0,
    ):
        self.recency_weight = recency_weight
        self.importance_weight = importance_weight
        self.relevance_weight = relevance_weight
        self.decay_days = decay_days

    async def retrieve(
        self,
        agent_id: Optional[str],
        query: str = "",
        tags: Optional[list[str]] = None,
        max_entries: int = 8,
        max_tokens: int = 1200,       # Approx token budget for memories
        chars_per_token: float = 4.0, # Conservative estimate
    ) -> list[MemoryEntry]:
        """
        Main entry point for memory retrieval.

        Args:
            agent_id: The calling agent's ID (retrieves agent + shared memories)
            query: Keyword/topic to search (used for relevance scoring)
            tags: Optional tag filter (pre-filters before ranking)
            max_entries: Hard limit on returned entries
            max_tokens: Token budget — stops adding entries when exceeded

        Returns:
            Ranked list of MemoryEntry, most relevant first.
        """
        # Step 1: Candidate pool — get more candidates than we'll return
        candidate_limit = max_entries * 4

        if tags:
            candidates = await memory_repo.search_by_tags(
                tags, agent_id=agent_id, limit=candidate_limit
            )
        elif query:
            candidates = await memory_repo.search_by_content(
                query, agent_id=agent_id, limit=candidate_limit
            )
        else:
            # No query — fall back to importance-ranked retrieval
            candidates = await memory_repo.get_most_important(
                agent_id=agent_id, limit=candidate_limit
            )

        if not candidates:
            logger.debug(f"MemoryRetriever: no candidates for agent={agent_id}")
            return []

        # Step 2: Score and rank
        scored = [
            (self._score(mem, query), mem)
            for mem in candidates
        ]
        scored.sort(key=lambda x: x[0], reverse=True)

        # Step 3: Apply token budget
        selected = []
        token_count = 0
        max_chars = max_tokens * chars_per_token

        for score, mem in scored[:max_entries]:
            entry_chars = len(mem.content)
            if token_count + entry_chars > max_chars and selected:
                break  # Would exceed budget — stop (but always include at least 1)
            selected.append(mem)
            token_count += entry_chars

        logger.debug(
            f"MemoryRetriever: {len(selected)}/{len(candidates)} entries "
            f"selected (~{int(token_count / chars_per_token)} tokens) "
            f"for agent={agent_id}"
        )

        return selected

    def _score(self, mem: MemoryEntry, query: str) -> float:
        """Compute composite relevance score for a memory entry."""
        recency = self._recency_score(mem.last_accessed)
        importance = mem.importance
        relevance = self._relevance_score(mem.content, mem.tags, query)

        return (
            self.recency_weight * recency
            + self.importance_weight * importance
            + self.relevance_weight * relevance
        )

    def _recency_score(self, last_accessed: datetime) -> float:
        """Exponential decay based on days since last access."""
        days_ago = (datetime.now() - last_accessed).total_seconds() / 86400
        return math.exp(-days_ago / self.decay_days)

    @staticmethod
    def _relevance_score(content: str, tags: list[str], query: str) -> float:
        """
        Simple keyword overlap score (V1).
        V2 will replace this with sentence-transformer cosine similarity.
        """
        if not query:
            return 0.5  # Neutral when no query

        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        tag_words = set(t.lower() for t in tags)

        all_doc_words = content_words | tag_words
        if not all_doc_words:
            return 0.0

        overlap = len(query_words & all_doc_words)
        return min(1.0, overlap / max(1, len(query_words)))

    def format_for_prompt(
        self, memories: list[MemoryEntry], max_chars_per_entry: int = 200
    ) -> str:
        """
        Format retrieved memories as a compact block for LLM context.

        Output example:
            [behavioral] User typically deviates after lunch (13:00–14:00).
            [preference] Prefers shorter task names in the schedule.
            [productivity] Best discipline days are Monday and Tuesday.
        """
        if not memories:
            return "(No relevant memories)"

        lines = []
        for mem in memories:
            content = mem.content
            if len(content) > max_chars_per_entry:
                content = content[:max_chars_per_entry] + "..."
            lines.append(f"[{mem.memory_type.value}] {content}")

        return "\n".join(lines)


# Singleton
memory_retriever = MemoryRetriever()
