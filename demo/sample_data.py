"""
Sample data for the public demo
===============================
Seeds a session database with about two weeks of made-up history plus today's
plan, so evaluators see charts, a streak and a realistic dashboard straight
away. Everything here is SAMPLE DATA: the UI labels it as such. It is
deterministic (same pattern for every session, relative to "today" in the
session's time zone) so evaluations are reproducible.

The plan for each day is the generic example day in
frontend/src/lib/dayTemplate.json.
"""

from __future__ import annotations

import json
import random
from datetime import date, timedelta

from config.settings import PROJECT_ROOT
from core import clock
from core.models import CLASS_POINTS, DailyMetrics, Task, TaskClass

TEMPLATE_PATH = PROJECT_ROOT / "frontend" / "src" / "lib" / "dayTemplate.json"
HISTORY_DAYS = 14

# Days (counted back from today) where the sample user answered "Not today",
# so the history shows one streak reset. Day 10 back -> current streak builds after it.
NOT_TODAY_DAYS_BACK = {10}


def load_template() -> list[dict]:
    return json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))


def _plan(day: date) -> list[Task]:
    return [
        Task(
            date=day,
            task=t["name"],
            start_time=t["start_time"],
            end_time=t["end_time"],
            task_class=TaskClass(t["task_class"]),
            points=CLASS_POINTS.get(t["task_class"], 30),
        )
        for t in load_template()
    ]


def _mark(task: Task, rng: random.Random, effort: float) -> Task:
    """Mark a block the way a real user would, with day-level 'effort' in 0..1."""
    if task.task_class == TaskClass.SLEEP:
        task.start_and_sit = task.complete_task = True
        task.be_attentive = True
        task.slider_val = 100
    else:
        task.start_and_sit = rng.random() < 0.55 + 0.4 * effort
        task.complete_task = task.start_and_sit and rng.random() < 0.45 + 0.45 * effort
        task.be_attentive = task.complete_task
        task.slider_val = int(45 + 50 * effort * rng.uniform(0.7, 1.0)) if task.be_attentive else 100
    task.completed = task.start_and_sit and task.complete_task and task.be_attentive
    return task


def _effort_for(days_back: int) -> float:
    """A gentle upward trend with a dip around the reset day."""
    base = 0.45 + 0.03 * (HISTORY_DAYS - days_back)
    if days_back in NOT_TODAY_DAYS_BACK:
        base -= 0.3
    return max(0.1, min(0.95, base))


async def seed_history(days: int = HISTORY_DAYS) -> None:
    """Replace the last `days` days (not today) with sample history and compute metrics."""
    from analytics.pipeline import pipeline
    from data.repositories.analytics_repo import analytics_repo
    from data.repositories.task_repo import task_repo
    from data.database import db

    today = clock.today()
    for days_back in range(days, 0, -1):  # oldest first: each day's streak builds on yesterday
        day = today - timedelta(days=days_back)
        rng = random.Random(1000 + days_back)
        effort = _effort_for(days_back)
        await task_repo.delete_for_date(day)
        await db.execute_write("DELETE FROM daily_analytics WHERE date = ?", (day.isoformat(),))
        await task_repo.bulk_upsert([_mark(t, rng, effort) for t in _plan(day)])
        if days_back in NOT_TODAY_DAYS_BACK:
            await analytics_repo.upsert_metrics(DailyMetrics(date=day, commitment_kept=False))
        await pipeline.run(day)


async def seed_today() -> None:
    """Today's plan: blocks that have already ended are partly marked; the rest are open."""
    from analytics.pipeline import pipeline
    from data.database import db
    from data.repositories.task_repo import task_repo

    today = clock.today()
    now = clock.now().time()
    rng = random.Random(7)
    tasks = []
    for t in _plan(today):
        if t.has_ended_by(now) and t.task_class != TaskClass.SLEEP:
            _mark(t, rng, 0.8)
        tasks.append(t)
    await task_repo.delete_for_date(today)
    await db.execute_write("DELETE FROM daily_analytics WHERE date = ?", (today.isoformat(),))
    await task_repo.bulk_upsert(tasks)
    await pipeline.run(today)


async def seed_all() -> None:
    await seed_history()
    await seed_today()
