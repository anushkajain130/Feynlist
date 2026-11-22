"""
Analytics Pipeline
==================
Orchestrates a full daily analytics computation:
  1. Load tasks for today
  2. Load yesterday's metrics for EWM weighting
  3. Run all metric formulas
  4. Persist results to daily_analytics table
  5. Update hourly_points for tasks completed this hour
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from loguru import logger

from core import clock
from core.models import DailyMetrics, Task, TaskClass
from data.repositories.task_repo import task_repo
from data.repositories.analytics_repo import analytics_repo
from analytics.metrics import (
    AlertnessMetric,
    DisciplineMetric,
    PSHoursMetric,
    AuraMetric,
    ConsistencyStreakMetric,
    PointsMetric,
)


class AnalyticsPipeline:
    """
    Runs the complete analytics computation for a given date.
    Idempotent — safe to call multiple times; each call overwrites the record.
    """

    async def run(self, target_date: Optional[date] = None) -> DailyMetrics:
        """
        Full pipeline: load → compute → persist → return.
        Defaults to today if no date given.
        """
        if target_date is None:
            target_date = clock.today()

        logger.info(f"Running analytics pipeline for {target_date}")

        # 1. Load tasks for the target date
        tasks = await task_repo.get_tasks_for_date(target_date)

        # Preserve the day's check-in answer, if any
        existing = await analytics_repo.get_metrics_for_date(target_date)
        commitment_kept = existing.commitment_kept if existing else None

        if not tasks and commitment_kept is None:
            logger.warning(f"No tasks found for {target_date}. Skipping analytics.")
            return DailyMetrics(date=target_date)

        # 2. Load yesterday's metrics for EWM weighting
        from datetime import timedelta
        yesterday_date = target_date - timedelta(days=1)
        yesterday = await analytics_repo.get_metrics_for_date(yesterday_date)

        # Yesterday's streak only carries over if yesterday itself counted
        # (a day with no record, or that didn't count, resets the base to 0).
        yesterday_streak = 0
        if yesterday and ConsistencyStreakMetric.day_counts(
            yesterday.commitment_kept, yesterday.tasks_completed, yesterday.tasks_total
        ):
            yesterday_streak = yesterday.retention_streak

        # 3. Compute all metrics
        now = clock.now().time()

        alertness = AlertnessMetric.compute(tasks, yesterday, now)
        discipline = DisciplineMetric.compute(
            tasks, yesterday, now, day_over=target_date < clock.today()
        )
        ps_hrs = PSHoursMetric.compute(tasks)
        tasks_completed = sum(1 for t in tasks if t.completed)
        retention_streak = ConsistencyStreakMetric.compute(
            yesterday_streak=yesterday_streak,
            commitment_kept=commitment_kept,
            tasks_completed=tasks_completed,
            tasks_total=len(tasks),
            day_in_progress=target_date >= clock.today(),
        )
        study_planned = any(t.task_class == TaskClass.ACADEMICS_SELFSTUDY for t in tasks)
        aura = AuraMetric.compute(
            discipline, ps_hrs, retention_streak, study_planned=study_planned
        )
        total_points = PointsMetric.compute_total(tasks)

        # 4. Assemble metrics object
        metrics = DailyMetrics(
            date=target_date,
            alertness=alertness,
            discipline=discipline,
            ps_hrs=ps_hrs,
            aura=aura,
            retention_streak=retention_streak,
            total_points=total_points,
            tasks_completed=tasks_completed,
            tasks_total=len(tasks),
            commitment_kept=commitment_kept,
        )

        # 5. Persist (single write — fixes V0 double-write bug)
        await analytics_repo.upsert_metrics(metrics)

        logger.info(
            f"Analytics for {target_date}: "
            f"discipline={discipline:.1f}% alertness={alertness:.1f}% "
            f"ps={ps_hrs:.1f}h aura={aura:.2f} streak={retention_streak}d"
        )

        return metrics

    async def log_hourly_completion(self, task: Task) -> None:
        """
        Call this when a subtask is toggled or task completed.
        Logs the earned points to the current hour's bucket.
        """
        current_hour = clock.now().hour
        earned = PointsMetric.compute_for_task(task)
        if earned > 0:
            await analytics_repo.log_hourly_point(clock.today(), current_hour, earned)


# Singleton
pipeline = AnalyticsPipeline()
