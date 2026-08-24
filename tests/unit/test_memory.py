"""
Unit Tests: Memory System
=========================
Tests SessionMemory, MemoryRetriever scoring, and prompt formatting.
No database I/O.
"""

import math
import pytest
from datetime import datetime, timedelta

from memory.short_term import SessionMemory
from memory.retriever import MemoryRetriever
from core.models import AgentId, AgentMessage, MemoryEntry, MemoryType, EventType, CallPriority


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def make_message(content="Hello", agent_id=AgentId.FREYA) -> AgentMessage:
    return AgentMessage(
        agent_id=agent_id,
        content=content,
        triggered_by=EventType.SCHEDULED_CHECKIN,
    )


def make_memory(
    content="Test memory",
    importance=0.5,
    memory_type=MemoryType.FACTUAL,
    tags=None,
    days_ago=0,
) -> MemoryEntry:
    last_accessed = datetime.now() - timedelta(days=days_ago)
    entry = MemoryEntry(
        agent_id="freya",
        memory_type=memory_type,
        content=content,
        tags=tags or [],
        importance=importance,
    )
    entry.last_accessed = last_accessed
    return entry


# =============================================================================
# SESSION MEMORY TESTS
# =============================================================================

class TestSessionMemory:

    def test_add_and_retrieve(self):
        mem = SessionMemory(AgentId.FREYA, max_size=10)
        msg = make_message("You missed yoga again.")
        mem.add(msg)
        recent = mem.get_recent(5)
        assert len(recent) == 1
        assert recent[0].content == "You missed yoga again."

    def test_max_size_enforcement(self):
        mem = SessionMemory(AgentId.FREYA, max_size=3)
        for i in range(5):
            mem.add(make_message(f"Message {i}"))
        # Only last 3 should remain
        assert mem.size() == 3
        contents = [m.content for m in mem.get_all()]
        assert "Message 2" in contents
        assert "Message 3" in contents
        assert "Message 4" in contents
        assert "Message 0" not in contents

    def test_get_recent_n(self):
        mem = SessionMemory(AgentId.FREYA, max_size=10)
        for i in range(6):
            mem.add(make_message(f"Msg {i}"))
        recent = mem.get_recent(3)
        assert len(recent) == 3
        assert recent[-1].content == "Msg 5"

    def test_clear(self):
        mem = SessionMemory(AgentId.FREYA)
        mem.add(make_message("Test"))
        mem.clear()
        assert mem.size() == 0

    def test_is_full(self):
        mem = SessionMemory(AgentId.FREYA, max_size=2)
        assert not mem.is_full()
        mem.add(make_message("1"))
        mem.add(make_message("2"))
        assert mem.is_full()

    def test_format_for_prompt(self):
        mem = SessionMemory(AgentId.FREYA)
        mem.add(make_message("You're falling behind on math."))
        formatted = mem.format_for_prompt()
        assert "Freya" in formatted
        assert "math" in formatted

    def test_format_empty(self):
        mem = SessionMemory(AgentId.FREYA)
        formatted = mem.format_for_prompt()
        assert "No recent conversation" in formatted

    def test_format_truncates_long_messages(self):
        mem = SessionMemory(AgentId.FREYA)
        long_msg = "x" * 500
        mem.add(make_message(long_msg))
        formatted = mem.format_for_prompt(max_chars_per_msg=100)
        assert "..." in formatted
        assert len(formatted) < 200  # Should be truncated

    def test_consolidation_text(self):
        mem = SessionMemory(AgentId.FREYA)
        mem.add(make_message("You need to focus."))
        text = mem.to_consolidation_text()
        assert "Session on" in text
        assert "focus" in text


# =============================================================================
# MEMORY RETRIEVER TESTS
# =============================================================================

class TestMemoryRetriever:

    def setup_method(self):
        self.retriever = MemoryRetriever()

    def test_recency_score_recent_high(self):
        score = self.retriever._recency_score(datetime.now())
        assert score > 0.9  # Just accessed = high score

    def test_recency_score_old_low(self):
        old_time = datetime.now() - timedelta(days=30)
        score = self.retriever._recency_score(old_time)
        # After 30 days with decay=14: exp(-30/14) ≈ 0.117
        assert score < 0.2

    def test_recency_score_decay(self):
        score_1d = self.retriever._recency_score(datetime.now() - timedelta(days=1))
        score_7d = self.retriever._recency_score(datetime.now() - timedelta(days=7))
        score_14d = self.retriever._recency_score(datetime.now() - timedelta(days=14))
        # Should decrease monotonically
        assert score_1d > score_7d > score_14d

    def test_relevance_perfect_match(self):
        score = MemoryRetriever._relevance_score(
            "user deviates in the afternoon", ["deviation", "afternoon"], "afternoon deviation"
        )
        assert score == 1.0

    def test_relevance_no_match(self):
        score = MemoryRetriever._relevance_score(
            "user loves morning yoga", ["morning", "yoga"], "deviation phone"
        )
        assert score == 0.0

    def test_relevance_partial_match(self):
        score = MemoryRetriever._relevance_score(
            "user tends to skip tasks", [], "skip afternoon"
        )
        # "skip" matches, "afternoon" doesn't → 0.5
        assert score == pytest.approx(0.5)

    def test_relevance_no_query_neutral(self):
        score = MemoryRetriever._relevance_score("anything", [], "")
        assert score == 0.5  # Neutral when no query

    def test_score_composite(self):
        # High importance + recent + relevant should score high
        mem = make_memory(
            content="user deviates after lunch",
            importance=0.9,
            days_ago=0,
        )
        score = self.retriever._score(mem, "deviation afternoon lunch")
        assert score > 0.7

    def test_score_old_low_importance_irrelevant(self):
        mem = make_memory(
            content="user did yoga once",
            importance=0.1,
            days_ago=60,  # Very old
        )
        score = self.retriever._score(mem, "math academics study")
        assert score < 0.3

    def test_format_for_prompt(self):
        memories = [
            make_memory("User deviates at 2pm", importance=0.7,
                       memory_type=MemoryType.BEHAVIORAL),
            make_memory("User prefers short task names", importance=0.5,
                       memory_type=MemoryType.PREFERENCE),
        ]
        formatted = self.retriever.format_for_prompt(memories)
        assert "[behavioral]" in formatted
        assert "[preference]" in formatted
        assert "2pm" in formatted

    def test_format_empty(self):
        formatted = self.retriever.format_for_prompt([])
        assert "No relevant memories" in formatted

    def test_format_truncates_long_content(self):
        long_content = "A" * 500
        memories = [make_memory(long_content)]
        formatted = self.retriever.format_for_prompt(memories, max_chars_per_entry=100)
        assert "..." in formatted
