"""
Unit Tests: Tools
=================
Tests tool validation, permission checking, and schema contracts.
No database I/O — all repos are mocked.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date, time, datetime

from tools.base_tool import BaseTool, ToolContext
from tools.task_tools import (
    GetCurrentTasksTool, GetTaskSummaryTool,
    GetMissedTasksTool, GetCurrentTasksInput,
)
from tools.analytics_tools import GetDailyMetricsTool, GetTrendSummaryTool
from tools.memory_tools import StoreMemoryTool, RetrieveMemoryTool
from tools.time_tools import GetTimeContextTool
from tools.registry import ToolRegistry
from core.models import Task, TaskClass, DailyMetrics, MemoryEntry, MemoryType
from core.exceptions import ToolPermissionError, ToolNotFoundError


# ─── Helpers ──────────────────────────────────────────────────────────────────

def make_context(agent_id="freya") -> ToolContext:
    return ToolContext(agent_id=agent_id, user_id="test_user")


def make_task(task="Test", start="08:00", end="09:00", points=100,
              completed=False, task_class=TaskClass.UNSPECIFIED) -> Task:
    return Task(
        date=date.today(),
        task=task,
        start_time=start,
        end_time=end,
        points=points,
        completed=completed,
        task_class=task_class,
    )


# =============================================================================
# TOOL REGISTRY TESTS
# =============================================================================

class TestToolRegistry:

    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = GetCurrentTasksTool()
        registry.register(tool)
        retrieved = registry.get("get_current_tasks")
        assert retrieved is tool

    def test_get_unknown_raises(self):
        registry = ToolRegistry()
        with pytest.raises(ToolNotFoundError):
            registry.get("nonexistent_tool")

    def test_list_all(self):
        registry = ToolRegistry()
        registry.register(GetCurrentTasksTool())
        registry.register(GetTaskSummaryTool())
        names = registry.list_all()
        assert "get_current_tasks" in names
        assert "get_task_summary" in names

    def test_get_for_agent_filtered(self):
        registry = ToolRegistry()
        tool_all = GetCurrentTasksTool()
        tool_restricted = GetTaskSummaryTool()
        registry.register(tool_all)  # No restriction
        registry.register(tool_restricted, allowed_agents=["albedo"])
        freya_tools = registry.get_for_agent("freya")
        tool_names = [t.name for t in freya_tools]
        assert "get_current_tasks" in tool_names
        assert "get_task_summary" not in tool_names  # Restricted to albedo

    def test_get_for_agent_unrestricted(self):
        registry = ToolRegistry()
        registry.register(GetCurrentTasksTool())
        tools = registry.get_for_agent("any_agent")
        assert len(tools) == 1


# =============================================================================
# PERMISSION CHECKING
# =============================================================================

class TestToolPermissions:

    @pytest.mark.asyncio
    async def test_permission_denied_returns_failure(self):
        tool = GetCurrentTasksTool()
        tool.allowed_agents = ["albedo"]  # Only albedo allowed
        ctx = make_context(agent_id="freya")
        result = await tool.safe_execute({}, ctx)
        assert result.success is False
        assert "permission" in result.error.lower()

    @pytest.mark.asyncio
    async def test_permission_granted(self):
        tool = GetCurrentTasksTool()
        tool.allowed_agents = ["freya"]
        ctx = make_context(agent_id="freya")

        with patch(
            "tools.task_tools.task_repo.get_tasks_for_date",
            new=AsyncMock(return_value=[])
        ):
            result = await tool.safe_execute({}, ctx)
        assert result.success is True


# =============================================================================
# TASK TOOLS
# =============================================================================

class TestGetCurrentTasksTool:

    @pytest.mark.asyncio
    async def test_empty_day(self):
        tool = GetCurrentTasksTool()
        ctx = make_context()

        with patch(
            "tools.task_tools.task_repo.get_tasks_for_date",
            new=AsyncMock(return_value=[])
        ):
            result = await tool.safe_execute({}, ctx)

        assert result.success is True
        assert result.data["total_tasks"] == 0

    @pytest.mark.asyncio
    async def test_completion_percentage(self):
        tool = GetCurrentTasksTool()
        ctx = make_context()
        tasks = [
            make_task("Task A", "00:00", "01:00", completed=True),
            make_task("Task B", "01:00", "02:00", completed=True),
            make_task("Task C", "02:00", "03:00", completed=False),
            make_task("Task D", "23:00", "23:59", completed=False),  # Future
        ]

        with patch(
            "tools.task_tools.task_repo.get_tasks_for_date",
            new=AsyncMock(return_value=tasks)
        ):
            result = await tool.safe_execute({}, ctx)

        assert result.success is True
        assert result.data["completed_count"] == 2
        assert result.data["total_tasks"] == 4


class TestGetMissedTasksTool:

    @pytest.mark.asyncio
    async def test_identifies_missed_tasks(self):
        tool = GetMissedTasksTool()
        ctx = make_context()
        # Past task, not completed, not deviated class
        missed = make_task("Math", "00:01", "00:02",
                           task_class=TaskClass.ACADEMICS_SELFSTUDY)
        future = make_task("Yoga", "23:00", "23:59")

        with patch(
            "tools.task_tools.task_repo.get_tasks_for_date",
            new=AsyncMock(return_value=[missed, future])
        ):
            result = await tool.safe_execute({}, ctx)

        assert result.success is True
        assert result.data["missed_count"] == 1

    @pytest.mark.asyncio
    async def test_deviated_not_counted_as_missed(self):
        tool = GetMissedTasksTool()
        ctx = make_context()
        deviated = make_task("Something", "00:01", "00:02",
                             task_class=TaskClass.DEVIATED)

        with patch(
            "tools.task_tools.task_repo.get_tasks_for_date",
            new=AsyncMock(return_value=[deviated])
        ):
            result = await tool.safe_execute({}, ctx)

        assert result.data["missed_count"] == 0


# =============================================================================
# MEMORY TOOLS
# =============================================================================

class TestStoreMemoryTool:

    @pytest.mark.asyncio
    async def test_store_creates_entry(self):
        tool = StoreMemoryTool()
        ctx = make_context()

        with patch(
            "tools.memory_tools.memory_repo.save",
            new=AsyncMock(return_value=None)
        ):
            result = await tool.safe_execute(
                {
                    "content": "User tends to deviate around 2pm",
                    "memory_type": "behavioral",
                    "tags": ["deviation", "afternoon"],
                    "importance": 0.7,
                },
                ctx
            )

        assert result.success is True
        assert "memory_id" in result.data
        assert result.data["stored"] is True

    @pytest.mark.asyncio
    async def test_store_invalid_type_fallback(self):
        tool = StoreMemoryTool()
        ctx = make_context()

        with patch(
            "tools.memory_tools.memory_repo.save",
            new=AsyncMock(return_value=None)
        ):
            result = await tool.safe_execute(
                {"content": "Some fact", "memory_type": "invalid_type"},
                ctx
            )

        assert result.success is True  # Falls back to 'factual'


class TestRetrieveMemoryTool:

    @pytest.mark.asyncio
    async def test_returns_formatted_results(self):
        tool = RetrieveMemoryTool()
        ctx = make_context()
        fake_mem = MemoryEntry(
            agent_id="freya",
            memory_type=MemoryType.BEHAVIORAL,
            content="User deviates at 2pm",
            tags=["deviation"],
            importance=0.7,
        )

        with patch(
            "tools.memory_tools.memory_repo.search_by_content",
            new=AsyncMock(return_value=[fake_mem])
        ), patch(
            "tools.memory_tools.memory_repo.mark_accessed",
            new=AsyncMock(return_value=None)
        ):
            result = await tool.safe_execute(
                {"query": "deviation afternoon"}, ctx
            )

        assert result.success is True
        assert result.data["total_found"] == 1
        assert result.data["memories"][0]["type"] == "behavioral"


# =============================================================================
# INPUT VALIDATION
# =============================================================================

class TestInputValidation:

    @pytest.mark.asyncio
    async def test_invalid_date_format_fails_gracefully(self):
        tool = GetCurrentTasksTool()
        ctx = make_context()
        result = await tool.safe_execute({"target_date": "not-a-date"}, ctx)
        # Should fail with a validation error, not a crash
        assert result.success is False

    @pytest.mark.asyncio
    async def test_importance_out_of_range(self):
        tool = StoreMemoryTool()
        ctx = make_context()
        result = await tool.safe_execute(
            {"content": "test", "importance": 1.5},  # > 1.0
            ctx
        )
        assert result.success is False
        assert "validation" in result.error.lower()
