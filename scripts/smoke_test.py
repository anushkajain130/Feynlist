"""
Smoke Test — end-to-end pipeline check
======================================
Runs against a throwaway SQLite database (never your real data) and checks:

  1. Database initialises and a sample day can be saved and read back
  2. Analytics pipeline computes metrics for that day
  3. Tool registry executes a tool
  4. Event bus + rules engine wiring
  5. Live LLM call (Freya) — only if GEMINI_API_KEY is set; otherwise SKIPPED

Every check reports PASS, FAIL or SKIP with a reason. The summary never says
"all passed" when something was skipped or failed.

Exit codes:
  0  no failures (skips allowed, and listed)
  1  at least one check failed
  2  no failures, but a skip happened and --require-llm was given

Run with:
    python -m scripts.smoke_test                # LLM step skipped without a key
    python -m scripts.smoke_test --require-llm  # treat a skipped LLM call as not OK
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Use a throwaway database BEFORE any app module reads settings.
_TMP = tempfile.TemporaryDirectory(prefix="feynlist-smoke-")
os.environ["DATABASE_PATH"] = str(Path(_TMP.name) / "smoke.db")

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


@dataclass
class Result:
    name: str
    status: str
    detail: str


async def check_database() -> Result:
    import json
    from core.models import Task, TaskClass
    from data.database import db
    from data.repositories.task_repo import task_repo

    await db.initialize()
    template = json.loads((ROOT / "frontend" / "src" / "lib" / "dayTemplate.json").read_text())
    tasks = [
        Task(date=date.today(), task=t["name"], start_time=t["start_time"], end_time=t["end_time"],
             task_class=TaskClass(t["task_class"]), points=50)
        for t in template
    ]
    await task_repo.bulk_upsert(tasks)
    loaded = await task_repo.get_tasks_for_date(date.today())
    if len(loaded) != len(tasks):
        return Result("database", FAIL, f"saved {len(tasks)} tasks, read back {len(loaded)}")
    return Result("database", PASS, f"saved and read back {len(loaded)} tasks")


async def check_analytics() -> Result:
    from analytics.pipeline import pipeline
    m = await pipeline.run(date.today())
    if m is None or m.tasks_total == 0:
        return Result("analytics", FAIL, "pipeline returned no metrics for a day with tasks")
    return Result("analytics", PASS,
                  f"discipline={m.discipline:.1f}% alertness={m.alertness:.1f}% "
                  f"aura={m.aura:.2f} streak={m.retention_streak}d")


async def check_tools() -> Result:
    from core.startup import _register_tools
    from tools.base_tool import ToolContext
    from tools.registry import tool_registry

    _register_tools()
    res = await tool_registry.execute("get_task_summary", {}, ToolContext(agent_id="freya"))
    if not res.success:
        return Result("tools", FAIL, f"get_task_summary failed: {res.error}")
    return Result("tools", PASS, f"{len(tool_registry.list_all())} tools registered; get_task_summary ok")


async def check_events() -> Result:
    from agents.orchestrator import orchestrator
    from core.startup import _wire_event_bus
    from events.rules_engine import register_default_rules, rules_engine

    await orchestrator.initialize()
    _wire_event_bus()
    register_default_rules(orchestrator)
    n = len(rules_engine.list_rules())
    if n == 0:
        return Result("events", FAIL, "no rules registered")
    return Result("events", PASS, f"{n} rules registered")


async def check_llm() -> Result:
    from agents.runtime import AgentRuntime
    from config.settings import settings
    from core.exceptions import AgentRuntimeError
    from core.models import AgentId, EventType

    if not settings.has_api_key:
        return Result("live_llm", SKIP, "no GEMINI_API_KEY set; live call not attempted")
    freya = AgentRuntime(AgentId.FREYA)
    try:
        await freya.initialize()
        msg = await freya.invoke(
            user_message="Hey, how's my day looking so far?",
            triggered_by=EventType.USER_DIRECT_MESSAGE,
            bypass_cooldown=True,
        )
    except AgentRuntimeError as e:
        reason = getattr(e, "reason", "error")
        return Result("live_llm", FAIL, f"live call failed ({reason})")
    if not msg.content or msg.content == "...":
        return Result("live_llm", FAIL, "model returned an empty reply")
    return Result("live_llm", PASS, f"{freya.model_name} replied ({len(msg.content)} chars): {msg.content[:120]!r}")


CHECKS = [check_database, check_analytics, check_tools, check_events, check_llm]


async def run_smoke_test(require_llm: bool = False) -> int:
    from loguru import logger
    logger.remove()
    logger.add(sys.stderr, level="WARNING")

    results: list[Result] = []
    for check in CHECKS:
        try:
            results.append(await check())
        except Exception as e:  # a crash is a failure, not a pass
            results.append(Result(check.__name__.removeprefix("check_"), FAIL, f"exception: {e}"))

    icons = {PASS: "PASS", FAIL: "FAIL", SKIP: "SKIP"}
    print("=" * 60)
    print("FEYNLIST SMOKE TEST (temporary database)")
    print("=" * 60)
    for r in results:
        print(f"  [{icons[r.status]}] {r.name}: {r.detail}")

    passed = sum(r.status == PASS for r in results)
    failed = [r for r in results if r.status == FAIL]
    skipped = [r for r in results if r.status == SKIP]
    print("-" * 60)
    print(f"  {passed} passed, {len(failed)} failed, {len(skipped)} skipped")

    if failed:
        print("RESULT: FAILED: " + ", ".join(r.name for r in failed))
        code = 1
    elif skipped and require_llm:
        print("RESULT: INCOMPLETE: skipped with --require-llm: " + ", ".join(r.name for r in skipped))
        code = 2
    elif skipped:
        print("RESULT: PASSED WITH SKIPS: " + ", ".join(r.name for r in skipped) + " not tested")
        code = 0
    else:
        print("RESULT: PASSED: every check ran and passed")
        code = 0
    print("=" * 60)
    return code


if __name__ == "__main__":
    sys.exit(asyncio.run(run_smoke_test(require_llm="--require-llm" in sys.argv)))
