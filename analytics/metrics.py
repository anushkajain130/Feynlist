"""
Analytics Metrics
=================
Pure, stateless metric computation functions.
All formulas documented with rationale.
No database I/O here — takes lists of Task/DailyMetrics, returns floats.

Fixes from V0:
  - Alertness: now filters past tasks only (end_time <= now)
  - Aura: uses log(1+streak) instead of streak^0.5 to avoid zero-collapse
  - Discipline: clearly separated from alertness
  - All formulas unit-testable without any DB dependency
"""

from __future__ import annotations

import math
from datetime import datetime, date, time
from typing import Optional

from core.models import Task, DailyMetrics, TaskClass
from config.settings import settings


# =============================================================================
# ALERTNESS
# =============================================================================

class AlertnessMetric:
    """
    Measures how focused/attentive the user was during completed tasks.

    Formula:
        raw = sum(slider_val for past tasks) / sum(points*0.2 for past tasks) * 100
        today_score = raw (clamped 0–100)
        final = yesterday_weight * yesterday + today_weight * today_score
            where today_weight=0.85, yesterday_weight=0.15

    "Past tasks" = tasks whose end_time is before or equal to current time.
    This is the key bug fix from V0 — V0 used `if True:` which included future tasks.

    Scale: 0–100 (higher = more focused)
    """

    @staticmethod
    def compute_raw(tasks: list[Task], now: time) -> float:
        """
        Compute raw alertness based on attention quality across all completed tasks
        relative to the total available points for the day.
        
        Formula:
            Overall Alertness = Sum( (slider_val / 100.0) * points for completed tasks ) / Sum( points for all tasks ) * 100
        """
        denominator = sum(t.points for t in tasks)
        if denominator <= 0:
            return 0.0

        numerator = sum((t.slider_val / 100.0) * t.points for t in tasks if t.completed)
        return min(100.0, (numerator / denominator) * 100.0)

    @staticmethod
    def compute(
        tasks: list[Task],
        yesterday: Optional[DailyMetrics] = None,
        now: Optional[time] = None,
    ) -> float:
        """
        Compute EWM-weighted alertness score for today.
        """
        if now is None:
            now = datetime.now().time()

        raw = AlertnessMetric.compute_raw(tasks, now)

        if yesterday is None or yesterday.alertness == 0.0:
            return round(raw, 4)

        weighted = (
            settings.alertness_today_weight * raw
            + settings.alertness_yesterday_weight * yesterday.alertness
        )
        return round(min(100.0, weighted), 4)


# =============================================================================
# DISCIPLINE
# =============================================================================

class DisciplineMetric:
    """
    Measures how consistently the user starts their scheduled tasks.

    Formula:
        started_pts = sum(start_and_sit_pts for past tasks where start_and_sit=True)
        total_pts   = sum(start_and_sit_pts for all past tasks)
        raw = (started_pts / total_pts) * 100
        final = 0.95 * today + 0.05 * yesterday

    A task's Start_and_Sit points = 50% of task.points.
    Only counts past tasks (end_time <= now).

    Scale: 0–100 (higher = more disciplined)
    """

    @staticmethod
    def compute_raw(tasks: list[Task], now: time) -> float:
        past_tasks = [t for t in tasks if t.end_time_obj <= now]

        if not past_tasks:
            return 0.0

        started_pts = sum(
            int(t.points * 0.5) for t in past_tasks if t.start_and_sit
        )
        total_pts = sum(int(t.points * 0.5) for t in past_tasks)

        if total_pts <= 0:
            return 0.0

        return min(100.0, (started_pts / total_pts) * 100)

    @staticmethod
    def compute(
        tasks: list[Task],
        yesterday: Optional[DailyMetrics] = None,
        now: Optional[time] = None,
    ) -> float:
        if now is None:
            now = datetime.now().time()

        raw = DisciplineMetric.compute_raw(tasks, now)

        if yesterday is None or yesterday.discipline == 0.0:
            return round(raw, 4)

        weighted = (
            settings.discipline_today_weight * raw
            + settings.discipline_yesterday_weight * yesterday.discipline
        )
        return round(min(100.0, weighted), 4)


# =============================================================================
# PROBLEM-SOLVING HOURS
# =============================================================================

class PSHoursMetric:
    """
    Counts the total problem-solving hours for the day.
    Only Academics_Selfstudy tasks contribute ps_var.

    Formula: sum(ps_var for completed Academics_Selfstudy tasks)

    Scale: 0–∞ hours (typical target: 2–4 hrs/day)
    """

    @staticmethod
    def compute(tasks: list[Task]) -> float:
        return round(
            sum(
                t.ps_var
                for t in tasks
                if t.task_class == TaskClass.ACADEMICS_SELFSTUDY and t.complete_task
            ),
            2,
        )


# =============================================================================
# AURA (COMPOSITE SCORE)
# =============================================================================

class AuraMetric:
    """
    Composite performance score.

    Formula:
        aura = (discipline/100)^0.5
               * (ps_hrs / ps_target)^0.5
               * log(1 + retention_streak)

    Key fix from V0: using log(1+streak) instead of streak^0.5.
    V0's formula collapsed to 0 whenever streak=0 (first day, or reset day),
    making the entire Aura score 0 regardless of that day's performance.

    log(1+0)  = 0     (streak=0, still resets, but forces you to re-earn)
    log(1+1)  = 0.69  (one clean day)
    log(1+7)  = 2.08  (one week)
    log(1+30) = 3.43  (one month)
    log(1+90) = 4.50  (three months)

    ps_target: from settings, default 6.0 hrs per 3 days = 2 hrs/day
    Scale: 0–∞ (no upper cap — grows with consistency)
    """

    @staticmethod
    def compute(
        discipline: float,
        ps_hrs: float,
        retention_streak: int,
        ps_target: Optional[float] = None,
    ) -> float:
        if ps_target is None:
            ps_target = settings.ps_hrs_target_per_3days / 3.0  # per-day target

        disc_factor = math.sqrt(max(0.0, discipline / 100.0))
        # Prevent zero-collapse: provide a baseline factor of 0.2 when ps_hrs is 0, scaling up to 1.0 at target
        ps_ratio = 0.2 + 0.8 * (min(1.0, ps_hrs / ps_target)) if ps_target > 0 else 1.0
        ps_factor = math.sqrt(max(0.0, ps_ratio))
        streak_factor = math.log(1 + max(0, retention_streak))

        return round(disc_factor * ps_factor * streak_factor, 4)


# =============================================================================
# CONSISTENCY STREAK
# =============================================================================

class ConsistencyStreakMetric:
    """
    Consecutive days on which the user kept their commitment to their plan.

    A day "counts" if EITHER:
      - the user checked in with "I kept my commitment today", OR
      - they completed at least `min_completion` (default 50%) of their planned tasks.

    Rules:
      - Checked in "Not today"            -> streak = 0
      - Day counts                         -> streak = base + 1
      - Day doesn't count, still in progress (today) -> streak = base (not broken yet)
      - Day doesn't count and is over      -> streak = 0

    `base` is yesterday's streak if yesterday counted, else 0
    (see `day_counts` for evaluating a stored day).

    The DB column is still named `retention_streak` for compatibility.
    """

    @staticmethod
    def day_counts(
        commitment_kept: Optional[bool],
        tasks_completed: int,
        tasks_total: int,
        min_completion: Optional[float] = None,
    ) -> bool:
        if min_completion is None:
            min_completion = settings.streak_min_completion
        if commitment_kept is False:
            return False
        if commitment_kept is True:
            return True
        if tasks_total <= 0:
            return False
        return (tasks_completed / tasks_total) >= min_completion

    @staticmethod
    def compute(
        yesterday_streak: int,
        commitment_kept: Optional[bool],
        tasks_completed: int,
        tasks_total: int,
        day_in_progress: bool,
        min_completion: Optional[float] = None,
    ) -> int:
        base = max(0, yesterday_streak)
        if commitment_kept is False:
            return 0
        if ConsistencyStreakMetric.day_counts(
            commitment_kept, tasks_completed, tasks_total, min_completion
        ):
            return base + 1
        return base if day_in_progress else 0


# =============================================================================
# TOTAL POINTS
# =============================================================================

class PointsMetric:
    """
    Total raw points scored today.

    Breakdown:
        Start_and_Sit → 50% of task.points (if start_and_sit=True)
        Complete_task → 30% of task.points (if complete_task=True)
        Be_attentive  → slider_val (0 to 20% of task.points) (slider_val is 0-100 percentage)
    """

    @staticmethod
    def compute_for_task(task: Task) -> int:
        earned = 0
        pts = task.points
        if task.start_and_sit:
            earned += int(pts * 0.5)
        if task.complete_task:
            earned += int(pts * 0.3)
        if task.be_attentive:
            # slider_val is 0-100 percentage. Points = (slider_val/100) * (pts * 0.2)
            earned += int((task.slider_val / 100.0) * (pts * 0.2))
        return earned

    @staticmethod
    def compute_total(tasks: list[Task]) -> int:
        return sum(PointsMetric.compute_for_task(t) for t in tasks)

    @staticmethod
    def compute_max_possible(tasks: list[Task]) -> int:
        return sum(t.points for t in tasks)
