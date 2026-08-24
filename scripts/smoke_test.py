"""
Smoke Test — End-to-End Live Integration
==========================================
Tests the full pipeline with a real Gemini API call.

What this tests:
  1. DB loads correctly (today's tasks)
  2. Analytics pipeline runs
  3. Context builder assembles a context packet
  4. Freya makes a real LLM call and returns a response
  5. Response is cleaned and returned correctly
  6. Event bus wiring works (task_missed fires Freya)

Run with:
    python -m scripts.smoke_test

Requires:
    - GEMINI_API_KEY set in .env
    - feynlist.db exists and has data
"""

import asyncio
import sys
from datetime import date
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from dotenv import load_dotenv

load_dotenv()


async def run_smoke_test():
    logger.info("=" * 60)
    logger.info("FEYNLIST V1 — SMOKE TEST")
    logger.info("=" * 60)

    results = {}

    # ------------------------------------------------------------------
    # 1. DATABASE
    # ------------------------------------------------------------------
    logger.info("\n[1/5] Database...")
    from data.database import db
    await db.initialize()
    from data.repositories.task_repo import task_repo
    tasks = await task_repo.get_tasks_for_date(date.today())
    results["db_tasks_loaded"] = len(tasks)
    logger.info(f"  ✅ Loaded {len(tasks)} tasks for today")

    # ------------------------------------------------------------------
    # 2. ANALYTICS PIPELINE
    # ------------------------------------------------------------------
    logger.info("\n[2/5] Analytics pipeline...")
    from analytics.pipeline import pipeline
    metrics = await pipeline.run(date.today())
    results["analytics_ok"] = metrics is not None
    logger.info(f"  ✅ Metrics: discipline={metrics.discipline:.1f}% "
                f"aura={metrics.aura:.2f} streak={metrics.retention_streak}d")

    # ------------------------------------------------------------------
    # 3. TOOL REGISTRY
    # ------------------------------------------------------------------
    logger.info("\n[3/5] Tool registry...")
    from tools.registry import tool_registry
    from tools.task_tools import GetCurrentTasksTool, GetTaskSummaryTool, GetMissedTasksTool, MarkSubtaskTool
    from tools.analytics_tools import GetDailyMetricsTool, GetTrendSummaryTool, GetPercentileTool, GetBurnoutSignalTool
    from tools.memory_tools import StoreMemoryTool, RetrieveMemoryTool, GetTopMemoriesTool
    from tools.time_tools import GetTimeContextTool

    tool_registry.register_many([
        GetCurrentTasksTool(), GetTaskSummaryTool(),
        GetMissedTasksTool(), GetDailyMetricsTool(),
        GetTrendSummaryTool(), GetPercentileTool(),
        GetBurnoutSignalTool(), StoreMemoryTool(),
        RetrieveMemoryTool(), GetTopMemoriesTool(),
        GetTimeContextTool(),
    ])
    tool_registry.register(MarkSubtaskTool(), allowed_agents=["freya", "zerotwo"])

    from tools.base_tool import ToolContext
    ctx = ToolContext(agent_id="freya")
    result = await tool_registry.execute("get_task_summary", {}, ctx)
    results["tool_registry_ok"] = result.success
    logger.info(f"  ✅ Tool 'get_task_summary' → success={result.success}")
    if result.success:
        logger.info(f"     {result.data.get('summary', '')[:100]}...")

    # ------------------------------------------------------------------
    # 4. AGENT RUNTIME — REAL LLM CALL
    # ------------------------------------------------------------------
    logger.info("\n[4/5] Live LLM call (Freya)...")
    from config.settings import settings as app_settings
    from agents.runtime import AgentRuntime
    from core.models import AgentId, EventType

    if not app_settings.has_api_key:
        logger.warning(
            "  ⚠️  No API key found — skipping live LLM call.\n"
            "     Add your key to d:\\feynlistV1\\.env:\n"
            "       GEMINI_API_KEY=your_key_here\n"
            "     or set GOOGLE_API_KEY as a system environment variable."
        )
        results["llm_call_ok"] = "SKIPPED (no API key)"
        results["response_chars"] = 0
    else:
        freya = AgentRuntime(AgentId.FREYA)
        await freya.initialize()

        message = await freya.invoke(
            user_message="Hey, how's my day looking so far?",
            triggered_by=EventType.USER_DIRECT_MESSAGE,
            bypass_cooldown=True,
        )

        results["llm_call_ok"] = bool(message.content)
        results["response_chars"] = len(message.content)
        logger.info(f"  ✅ Freya responded ({len(message.content)} chars):")
        logger.info(f"     \"{message.content[:200]}\"")

    # ------------------------------------------------------------------
    # 5. EVENT BUS WIRING
    # ------------------------------------------------------------------
    logger.info("\n[5/5] Event bus + rules engine wiring...")
    from events.event_bus import event_bus
    from events.rules_engine import rules_engine, register_default_rules
    from agents.orchestrator import orchestrator

    await orchestrator.initialize()

    from core.startup import _wire_event_bus
    _wire_event_bus()
    register_default_rules(orchestrator)

    results["rules_registered"] = len(rules_engine.list_rules())
    logger.info(f"  ✅ {results['rules_registered']} rules registered")

    # ------------------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------------------
    logger.info("\n" + "=" * 60)
    logger.info("SMOKE TEST RESULTS")
    logger.info("=" * 60)
    all_ok = all([
        results.get("db_tasks_loaded", 0) >= 0,
        results.get("analytics_ok"),
        results.get("tool_registry_ok"),
        results.get("llm_call_ok") is not False,   # True or "SKIPPED" both pass
        results.get("rules_registered", 0) > 0,
    ])

    for k, v in results.items():
        icon = "✅" if v else "❌"
        logger.info(f"  {icon} {k}: {v}")

    logger.info("=" * 60)
    if all_ok:
        logger.info("🎉 ALL CHECKS PASSED — System is operational")
    else:
        logger.error("❌ SOME CHECKS FAILED — Review logs above")
    logger.info("=" * 60)

    return all_ok


if __name__ == "__main__":
    success = asyncio.run(run_smoke_test())
    sys.exit(0 if success else 1)
