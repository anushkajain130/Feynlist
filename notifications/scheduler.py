"""
Notification Scheduler
======================
APScheduler-based background scheduler.
Fires event triggers on a defined cadence throughout the day.

Jobs registered:
  - Every 20 min: emit_task_missed (catch missed tasks quickly)
  - Every 20 min: analytics pipeline run (keep metrics live)
  - Every 2 hrs:  emit_scheduled_checkin (ZeroTwo review)
  - 06:00 daily:  emit_day_start (Freya opens the day)
  - 23:00 daily:  emit_day_end (Anya closes the day + streak check)

Usage:
    from notifications.scheduler import scheduler
    await scheduler.start()
    # ... app runs ...
    await scheduler.stop()
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from notifications.triggers import (
    emit_task_missed,
    emit_scheduled_checkin,
    emit_day_start,
    emit_day_end,
    emit_burnout_check,
)
from analytics.pipeline import pipeline
from datetime import date


async def _run_analytics_pipeline() -> None:
    """Wrapper for the analytics pipeline job."""
    try:
        await pipeline.run(date.today())
    except Exception as e:
        logger.error(f"Scheduler: analytics pipeline failed: {e}")


async def _run_task_missed_check() -> None:
    try:
        await emit_task_missed()
    except Exception as e:
        logger.error(f"Scheduler: task_missed check failed: {e}")


async def _run_scheduled_checkin() -> None:
    try:
        await emit_scheduled_checkin()
    except Exception as e:
        logger.error(f"Scheduler: scheduled checkin failed: {e}")


async def _run_day_start() -> None:
    try:
        await emit_day_start()
    except Exception as e:
        logger.error(f"Scheduler: day_start failed: {e}")


async def _run_day_end() -> None:
    try:
        await emit_day_end()
    except Exception as e:
        logger.error(f"Scheduler: day_end failed: {e}")


class FeynlistScheduler:
    """
    Wraps APScheduler with Feynlist-specific jobs.
    Singleton — use the `scheduler` instance exported below.
    """

    def __init__(self):
        self._scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")
        self._running = False

    def setup_jobs(self) -> None:
        """Register all scheduled jobs. Call before start()."""

        # Every 20 minutes: check for missed tasks
        self._scheduler.add_job(
            _run_task_missed_check,
            trigger=IntervalTrigger(minutes=20),
            id="task_missed_check",
            name="Task Missed Checker",
            replace_existing=True,
        )

        # Every 20 minutes: recompute today's analytics
        self._scheduler.add_job(
            _run_analytics_pipeline,
            trigger=IntervalTrigger(minutes=20),
            id="analytics_pipeline",
            name="Analytics Pipeline",
            replace_existing=True,
        )

        # Every 2 hours: ZeroTwo scheduled checkin
        self._scheduler.add_job(
            _run_scheduled_checkin,
            trigger=IntervalTrigger(hours=2),
            id="scheduled_checkin",
            name="ZeroTwo Checkin",
            replace_existing=True,
        )

        # 06:00 IST daily: Day start
        self._scheduler.add_job(
            _run_day_start,
            trigger=CronTrigger(hour=6, minute=0, timezone="Asia/Kolkata"),
            id="day_start",
            name="Day Start",
            replace_existing=True,
        )

        # 23:00 IST daily: Day end review + burnout check
        self._scheduler.add_job(
            _run_day_end,
            trigger=CronTrigger(hour=23, minute=0, timezone="Asia/Kolkata"),
            id="day_end",
            name="Day End Review",
            replace_existing=True,
        )

        logger.info(f"Scheduler: {len(self._scheduler.get_jobs())} jobs registered.")

    async def start(self) -> None:
        """Start the scheduler. Call this once at application startup."""
        if self._running:
            return
        self.setup_jobs()
        self._scheduler.start()
        self._running = True
        logger.info("Scheduler: started.")

    async def stop(self) -> None:
        """Gracefully stop the scheduler. Call on application shutdown."""
        if not self._running:
            return
        self._scheduler.shutdown(wait=False)
        self._running = False
        logger.info("Scheduler: stopped.")

    def is_running(self) -> bool:
        return self._running

    def list_jobs(self) -> list[dict]:
        """Return a summary of all registered jobs."""
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else "N/A",
            }
            for job in self._scheduler.get_jobs()
        ]


# Singleton
scheduler = FeynlistScheduler()
