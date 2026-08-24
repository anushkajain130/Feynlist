"""
Application Startup
===================
Single entry point that initializes the entire Feynlist system in order.

Initialization sequence:
  1. Database (migrations)
  2. Tool Registry (register all tools)
  3. Orchestrator (initialize all 5 agent runtimes)
  4. Event Bus ← Rules Engine (wire rules to events)
  5. Scheduler (start background jobs)

Call startup() at the beginning of any entry point:
  - FastAPI lifespan
  - CLI runner
  - Test fixtures

Call shutdown() on graceful exit.
"""

from __future__ import annotations

from loguru import logger

from data.database import db
from tools.registry import tool_registry
from tools.task_tools import (
    GetCurrentTasksTool, GetTaskSummaryTool,
    GetMissedTasksTool, MarkSubtaskTool,
)
from tools.analytics_tools import (
    GetDailyMetricsTool, GetTrendSummaryTool,
    GetPercentileTool, GetBurnoutSignalTool,
)
from tools.memory_tools import (
    StoreMemoryTool, RetrieveMemoryTool, GetTopMemoriesTool,
)
from tools.time_tools import GetTimeContextTool
from agents.orchestrator import orchestrator
from events.event_bus import event_bus
from events.rules_engine import rules_engine, register_default_rules
from notifications.scheduler import scheduler


async def startup() -> None:
    """
    Initialize all Feynlist subsystems in the correct order.
    Idempotent — safe to call multiple times.
    """
    logger.info("=" * 50)
    logger.info("Feynlist V1 — starting up")
    logger.info("=" * 50)

    # 1. Database
    logger.info("Step 1/5: Initializing database...")
    await db.initialize()

    # 2. Tool Registry
    logger.info("Step 2/5: Registering tools...")
    _register_tools()

    # 3. Orchestrator
    logger.info("Step 3/5: Initializing agent runtimes...")
    await orchestrator.initialize()

    # 4. Event Bus + Rules Engine
    logger.info("Step 4/5: Wiring event bus to rules engine...")
    _wire_event_bus()
    register_default_rules(orchestrator)

    # 5. Scheduler
    logger.info("Step 5/5: Starting background scheduler...")
    await scheduler.start()

    logger.info("Feynlist V1 — startup complete ✅")
    logger.info(f"  Tools registered: {len(tool_registry.list_all())}")
    logger.info(f"  Rules registered: {len(rules_engine.list_rules())}")
    logger.info(f"  Scheduler jobs:   {len(scheduler.list_jobs())}")
    logger.info("=" * 50)


async def shutdown() -> None:
    """Graceful shutdown — consolidate sessions, stop scheduler."""
    logger.info("Feynlist V1 — shutting down...")
    await scheduler.stop()
    await orchestrator.end_day()
    logger.info("Feynlist V1 — shutdown complete.")


# ---------------------------------------------------------------------------
# TOOL REGISTRATION
# ---------------------------------------------------------------------------

def _register_tools() -> None:
    """Register all tools in the global registry."""

    # Task tools — available to all agents
    tool_registry.register_many([
        GetCurrentTasksTool(),
        GetTaskSummaryTool(),
        GetMissedTasksTool(),
    ])

    # Mark subtask — only Freya and ZeroTwo (they give direct commands)
    tool_registry.register(
        MarkSubtaskTool(),
        allowed_agents=["freya", "zerotwo"],
    )

    # Analytics tools — all agents
    tool_registry.register_many([
        GetDailyMetricsTool(),
        GetTrendSummaryTool(),
        GetPercentileTool(),
        GetBurnoutSignalTool(),
    ])

    # Memory tools — all agents
    tool_registry.register_many([
        StoreMemoryTool(),
        RetrieveMemoryTool(),
        GetTopMemoriesTool(),
    ])

    # Time tool — all agents
    tool_registry.register(GetTimeContextTool())

    logger.debug(f"Tools registered: {tool_registry.list_all()}")


# ---------------------------------------------------------------------------
# EVENT BUS WIRING
# ---------------------------------------------------------------------------

def _wire_event_bus() -> None:
    """
    Connect the event bus to the rules engine.
    Every event published goes through rule evaluation first.
    """
    from core.models import EventType

    # Wire ALL event types through the rules engine
    for event_type in EventType:
        event_bus.subscribe_handler(
            event_type,
            _make_rules_handler(event_type),
        )

    logger.debug("Event bus wired to rules engine for all event types.")


def _make_rules_handler(event_type):
    """Create an async handler that evaluates rules for a specific event type."""
    async def handler(event):
        await rules_engine.evaluate(event)
    handler.__name__ = f"rules_handler_{event_type.value}"
    return handler
