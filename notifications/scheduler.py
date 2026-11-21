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

from config.settings import settings
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
from core import clock


async def _run_analytics_pipeline() -> None:
    """Wrapper for the analytics pipeline job."""
    try:
        await pipeline.run(clock.today())
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
        self._scheduler = AsyncIOScheduler(timezone=settings.app_timezone or None)
        self._running = False

    def setup_jobs(self) -> None:
        """
        Register scheduled jobs. Call before start().

        The analytics job (no LLM) always runs. Jobs that make coaches speak on a
        timer call the model, so they are registered only with
        ENABLE_PROACTIVE_LLM=true and outside the public demo: with nobody
        present they would burn the free daily quota.
        """
        tz = settings.app_timezone or None

        # Every 20 minutes: recompute today's analytics (no LLM)
        self._scheduler.add_job(
            _run_analytics_pipeline,
            trigger=IntervalTrigger(minutes=20),
            id="analytics_pipeline",
            name="Analytics Pipeline",
            replace_existing=True,
        )

        if settings.enable_proactive_llm and not settings.demo_mode:
            # Every 20 minutes: check for missed tasks (Freya)
            self._scheduler.add_job(_run_task_missed_check, trigger=IntervalTrigger(minutes=20),
                                    id="task_missed_check", name="Task Missed Checker", replace_existing=True)
            # Every 2 hours: ZeroTwo scheduled check-in
            self._scheduler.add_job(_run_scheduled_checkin, trigger=IntervalTrigger(hours=2),
                                    id="scheduled_checkin", name="ZeroTwo Checkin", replace_existing=True)
            # 06:00 daily: day start (Freya)
            self._scheduler.add_job(_run_day_start, trigger=CronTrigger(hour=6, minute=0, timezone=tz),
                                    id="day_start", name="Day Start", replace_existing=True)
            # 23:00 daily: end-of-day review (Anya) + workload and streak checks
            self._scheduler.add_job(_run_day_end, trigger=CronTrigger(hour=23, minute=0, timezone=tz),
                                    id="day_end", name="Day End Review", replace_existing=True)
        else:
            logger.info("Scheduler: proactive LLM jobs off (ENABLE_PROACTIVE_LLM=false or demo mode).")

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
                "next_run": str(getattr(job, "next_run_time", None) or "N/A"),
            }
            for job in self._scheduler.get_jobs()
        ]


# Singleton
scheduler = FeynlistScheduler()
