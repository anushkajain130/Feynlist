"""
Memory Repository
=================
All database operations for the memory_entries table.
Handles both shared and agent-specific memory entries.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from loguru import logger

from core.models import MemoryEntry, MemoryType
from data.database import db, parse_json_field, dump_json_field


class MemoryRepository:
    """CRUD for the memory_entries table."""

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    async def get_by_id(self, memory_id: str) -> Optional[MemoryEntry]:
        row = await db.fetch_one(
            "SELECT * FROM memory_entries WHERE id = ?", (memory_id,)
        )
        return self._row_to_entry(row) if row else None

    async def get_for_agent(
        self,
        agent_id: Optional[str],
        include_shared: bool = True,
        limit: int = 50,
    ) -> list[MemoryEntry]:
        """
        Fetch memories for a specific agent.
        If include_shared=True, also returns shared (agent_id=NULL) memories.
        Ordered by importance DESC, then last_accessed DESC.
        """
        if include_shared:
            rows = await db.fetch_all(
                """
                SELECT * FROM memory_entries
                WHERE agent_id = ? OR agent_id IS NULL
                ORDER BY importance DESC, last_accessed DESC
                LIMIT ?
                """,
                (agent_id, limit),
            )
        else:
            rows = await db.fetch_all(
                """
                SELECT * FROM memory_entries
                WHERE agent_id = ?
                ORDER BY importance DESC, last_accessed DESC
                LIMIT ?
                """,
                (agent_id, limit),
            )
        return [self._row_to_entry(r) for r in rows]

    async def search_by_tags(
        self, tags: list[str], agent_id: Optional[str] = None, limit: int = 20
    ) -> list[MemoryEntry]:
        """
        Search memories that contain any of the given tags.
        SQLite JSON matching via LIKE (sufficient for V1; replace with FTS in V2).
        """
        all_results: list[MemoryEntry] = []
        for tag in tags:
            rows = await db.fetch_all(
                """
                SELECT * FROM memory_entries
                WHERE (agent_id = ? OR agent_id IS NULL)
                  AND tags LIKE ?
                ORDER BY importance DESC
                LIMIT ?
                """,
                (agent_id, f'%"{tag}"%', limit),
            )
            all_results.extend([self._row_to_entry(r) for r in rows])

        # Deduplicate by ID, preserve order
        seen = set()
        unique = []
        for entry in all_results:
            if entry.id not in seen:
                seen.add(entry.id)
                unique.append(entry)
        return unique[:limit]

    async def search_by_content(
        self, query: str, agent_id: Optional[str] = None, limit: int = 10
    ) -> list[MemoryEntry]:
        """
        Full-text keyword search on memory content.
        V1: LIKE-based. V2: SQLite FTS5 or vector embeddings.
        """
        rows = await db.fetch_all(
            """
            SELECT * FROM memory_entries
            WHERE (agent_id = ? OR agent_id IS NULL)
              AND content LIKE ?
            ORDER BY importance DESC, last_accessed DESC
            LIMIT ?
            """,
            (agent_id, f"%{query}%", limit),
        )
        return [self._row_to_entry(r) for r in rows]

    async def get_most_important(
        self, agent_id: Optional[str] = None, limit: int = 8
    ) -> list[MemoryEntry]:
        """Fetch top N entries by importance score."""
        rows = await db.fetch_all(
            """
            SELECT * FROM memory_entries
            WHERE (agent_id = ? OR agent_id IS NULL)
            ORDER BY importance DESC, access_count DESC
            LIMIT ?
            """,
            (agent_id, limit),
        )
        return [self._row_to_entry(r) for r in rows]

    async def get_recent(
        self, agent_id: Optional[str] = None, limit: int = 10
    ) -> list[MemoryEntry]:
        """Fetch most recently created memories."""
        rows = await db.fetch_all(
            """
            SELECT * FROM memory_entries
            WHERE (agent_id = ? OR agent_id IS NULL)
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (agent_id, limit),
        )
        return [self._row_to_entry(r) for r in rows]

    async def count_for_agent(self, agent_id: Optional[str]) -> int:
        """Count total memories for an agent."""
        row = await db.fetch_one(
            "SELECT COUNT(*) as c FROM memory_entries WHERE agent_id = ? OR agent_id IS NULL",
            (agent_id,),
        )
        return row["c"] if row else 0

    # ------------------------------------------------------------------
    # WRITE
    # ------------------------------------------------------------------

    async def save(self, entry: MemoryEntry) -> None:
        """Insert a new memory entry."""
        async with db.connection() as conn:
            await conn.execute(
                """
                INSERT OR IGNORE INTO memory_entries
                    (id, agent_id, memory_type, content, tags, importance,
                     created_at, last_accessed, access_count)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), 0)
                """,
                (
                    entry.id,
                    entry.agent_id,
                    entry.memory_type.value,
                    entry.content,
                    dump_json_field(entry.tags),
                    entry.importance,
                ),
            )
            await conn.commit()
        logger.debug(f"Saved memory [{entry.memory_type.value}]: {entry.content[:60]}...")

    async def bulk_save(self, entries: list[MemoryEntry]) -> None:
        """Insert multiple memories in a single transaction."""
        async with db.connection() as conn:
            await conn.executemany(
                """
                INSERT OR IGNORE INTO memory_entries
                    (id, agent_id, memory_type, content, tags, importance,
                     created_at, last_accessed, access_count)
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), 0)
                """,
                [
                    (
                        e.id, e.agent_id, e.memory_type.value, e.content,
                        dump_json_field(e.tags), e.importance,
                    )
                    for e in entries
                ],
            )
            await conn.commit()
        logger.info(f"Bulk saved {len(entries)} memory entries.")

    async def mark_accessed(self, memory_id: str) -> None:
        """Update last_accessed and increment access_count."""
        async with db.connection() as conn:
            await conn.execute(
                """
                UPDATE memory_entries
                SET last_accessed = datetime('now'), access_count = access_count + 1
                WHERE id = ?
                """,
                (memory_id,),
            )
            await conn.commit()

    async def update_importance(self, memory_id: str, importance: float) -> None:
        """Update the importance score of a memory entry."""
        async with db.connection() as conn:
            await conn.execute(
                "UPDATE memory_entries SET importance = ? WHERE id = ?",
                (max(0.0, min(1.0, importance)), memory_id),
            )
            await conn.commit()

    async def delete(self, memory_id: str) -> None:
        """Delete a memory entry (GDPR right to erasure)."""
        async with db.connection() as conn:
            await conn.execute(
                "DELETE FROM memory_entries WHERE id = ?", (memory_id,)
            )
            await conn.commit()
        logger.info(f"Deleted memory entry: {memory_id}")

    async def delete_all_for_agent(self, agent_id: str) -> int:
        """Delete all memories for a specific agent. Returns count deleted."""
        async with db.connection() as conn:
            async with conn.execute(
                "DELETE FROM memory_entries WHERE agent_id = ?", (agent_id,)
            ) as cursor:
                await conn.commit()
                return cursor.rowcount

    async def prune_low_importance(
        self, threshold: float = 0.2, keep_recent_days: int = 7
    ) -> int:
        """
        Remove old, low-importance memories to keep the database lean.
        Preserves anything created in the last keep_recent_days days.
        Returns count pruned.
        """
        async with db.connection() as conn:
            async with conn.execute(
                """
                DELETE FROM memory_entries
                WHERE importance < ?
                  AND created_at < datetime('now', ? || ' days')
                """,
                (threshold, f"-{keep_recent_days}"),
            ) as cursor:
                await conn.commit()
                count = cursor.rowcount
        if count:
            logger.info(f"Pruned {count} low-importance memory entries.")
        return count

    # ------------------------------------------------------------------
    # PRIVATE
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_entry(row) -> MemoryEntry:
        d = dict(row)
        return MemoryEntry(
            id=d["id"],
            agent_id=d.get("agent_id"),
            memory_type=MemoryType(d.get("memory_type", "factual")),
            content=d["content"],
            tags=parse_json_field(d.get("tags"), default=[]),
            importance=d.get("importance", 0.5),
            created_at=datetime.fromisoformat(d["created_at"]),
            last_accessed=datetime.fromisoformat(d["last_accessed"]),
            access_count=d.get("access_count", 0),
        )


# Singleton
memory_repo = MemoryRepository()
