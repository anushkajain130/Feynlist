"""
Analytics Trends
================
Multi-day trend computation over historical analytics data.
Answers questions like:
  - "What's my 7-day discipline trend?"
  - "When am I most productive in the day?"
  - "Am I showing burnout signals?"
  - "What's my procrastination pattern?"

All methods are async, reading from the analytics_repo.
Pure computation — no LLM calls here.
"""

from __future__ import annotations

import math
from datetime import date, timedelta
from dataclasses import dataclass
from typing import Optional

from loguru import logger

from core.models import DailyMetrics
from data.repositories.analytics_repo import analytics_repo
from data.repositories.task_repo import task_repo


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class TrendPoint:
    """A single (date, value) pair in a trend series."""
    date: date
    value: float


@dataclass
class ProcrastinationPattern:
    """Detected procrastination cycle in historical data."""
    detected: bool
    typical_hours: list[int]        # Hours when deviation typically happens
    avg_recovery_days: float        # Days until user bounces back
    trigger_classes: list[str]      # Task classes that trigger deviation
    description: str


@dataclass
class BurnoutSignal:
    """Output of the burnout detection algorithm."""
    detected: bool
    severity: str                   # "mild", "moderate", "severe"
    contributing_factors: list[str]
    recommendation: str


@dataclass
class WeeklyInsight:
    """Aggregated weekly performance summary."""
    week_start: date
    avg_discipline: float
    avg_alertness: float
    total_ps_hrs: float
    avg_aura: float
    best_day: Optional[date]
    worst_day: Optional[date]
    streak_delta: int               # Change in streak from start to end of week


# =============================================================================
# TREND ANALYZER
# =============================================================================

class TrendAnalyzer:
    """
    Computes multi-day trends and patterns from historical analytics data.
    Designed to power both the analytics dashboard and agent context.
    """

    # ------------------------------------------------------------------
    # BASIC TREND SERIES
    # ------------------------------------------------------------------

    async def get_metric_trend(
        self,
        metric: str,
        days: int = 7,
        end_date: Optional[date] = None,
    ) -> list[TrendPoint]:
        """
        Returns a time-series of a named metric over the last N days.

        Args:
            metric: One of 'alertness', 'discipline', 'ps_hrs', 'aura',
                    'retention_streak', 'total_points'
            days: Lookback window
            end_date: Defaults to today
        """
        if end_date is None:
            end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)

        records = await analytics_repo.get_metrics_for_range(start_date, end_date)
        records_by_date = {r.date: r for r in records}

        trend = []
        for i in range(days):
            d = start_date + timedelta(days=i)
            if d in records_by_date:
                value = getattr(records_by_date[d], metric, 0.0)
                trend.append(TrendPoint(date=d, value=float(value)))
            # Skip days with no data (gaps are intentional — not padded with zeros)

        return trend

    async def get_7day_summary(self) -> dict[str, float]:
        """
        Returns average of each metric over the last 7 days.
        Useful for agent context — quick snapshot without loading full series.
        """
        records = await analytics_repo.get_latest(7)
        if not records:
            return {
                "avg_discipline": 0.0,
                "avg_alertness": 0.0,
                "avg_ps_hrs": 0.0,
                "avg_aura": 0.0,
                "days_counted": 0,
            }

        n = len(records)
        return {
            "avg_discipline": round(sum(r.discipline for r in records) / n, 2),
            "avg_alertness": round(sum(r.alertness for r in records) / n, 2),
            "avg_ps_hrs": round(sum(r.ps_hrs for r in records) / n, 2),
            "avg_aura": round(sum(r.aura for r in records) / n, 2),
            "days_counted": n,
        }

    async def get_trend_direction(
        self, metric: str, days: int = 7
    ) -> str:
        """
        Returns "improving", "declining", or "stable" for a metric trend.
        Uses simple linear regression slope.
        """
        trend = await self.get_metric_trend(metric, days=days)
        if len(trend) < 3:
            return "stable"

        values = [p.value for p in trend]
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n

        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return "stable"

        slope = numerator / denominator

        # Threshold: slope > 1.5 = improving, < -1.5 = declining
        if slope > 1.5:
            return "improving"
        elif slope < -1.5:
            return "declining"
        else:
            return "stable"

    # ------------------------------------------------------------------
    # PEAK PRODUCTIVITY HOURS
    # ------------------------------------------------------------------

    async def get_best_productive_hours(
        self, lookback_days: int = 30
    ) -> list[int]:
        """
        Returns hours of the day (0–23) ranked best to worst by avg points.
        Derived from hourly_points table.
        """
        return await analytics_repo.get_best_productive_hours(lookback_days)

    async def get_productivity_heatmap(
        self, lookback_days: int = 14
    ) -> dict[int, float]:
        """
        Returns a dict mapping hour → avg_points_per_active_day.
        Used to render a 24-hour heatmap in the UI.
        """
        end = date.today()
        start = end - timedelta(days=lookback_days)

        hourly_data: dict[int, list[int]] = {h: [] for h in range(24)}

        current = start
        while current <= end:
            points = await analytics_repo.get_hourly_for_date(current)
            for hp in points:
                hourly_data[hp.hour].append(hp.points)
            current += timedelta(days=1)

        result = {}
        for hour, values in hourly_data.items():
            active_days = [v for v in values if v > 0]
            result[hour] = round(sum(active_days) / len(active_days), 1) if active_days else 0.0

        return result

    # ------------------------------------------------------------------
    # CONSISTENCY SCORE
    # ------------------------------------------------------------------

    async def get_consistency_score(self, days: int = 30) -> float:
        """
        Measures how consistently productive the user is day-over-day.

        Score = 1 - (standard_deviation / mean) of discipline over N days
        High consistency = low variance relative to mean.
        Returns 0–100 (higher = more consistent).
        """
        records = await analytics_repo.get_latest(days)
        if len(records) < 3:
            return 0.0

        values = [r.discipline for r in records if r.discipline > 0]
        if len(values) < 3:
            return 0.0

        mean = sum(values) / len(values)
        if mean == 0:
            return 0.0

        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std_dev = math.sqrt(variance)
        cv = std_dev / mean  # Coefficient of variation (lower = more consistent)

        # Map CV to 0–100 score (CV of 0 = 100 score, CV of 1 = 0 score)
        score = max(0.0, (1 - cv) * 100)
        return round(score, 2)

    # ------------------------------------------------------------------
    # PROCRASTINATION PATTERN DETECTION
    # ------------------------------------------------------------------

    async def detect_procrastination_pattern(
        self, lookback_days: int = 30
    ) -> ProcrastinationPattern:
        """
        Identifies recurring procrastination patterns from task history.

        Looks for:
        - Clustered Deviated task classes (multiple on same day)
        - Days where discipline < 30% (poor start rate)
        - Time-of-day clustering of deviations
        """
        end = date.today()
        start = end - timedelta(days=lookback_days)

        low_discipline_days: list[date] = []
        deviation_hours: list[int] = []
        deviation_classes: dict[str, int] = {}

        current = start
        while current <= end:
            tasks = await task_repo.get_tasks_for_date(current)
            metrics = await analytics_repo.get_metrics_for_date(current)

            if metrics and metrics.discipline < 30.0:
                low_discipline_days.append(current)

            for task in tasks:
                if task.task_class.value == "Deviated":
                    try:
                        h = int(task.start_time.split(":")[0])
                        deviation_hours.append(h)
                    except (ValueError, IndexError):
                        pass

                    sub = task.sub_class or "Unknown"
                    deviation_classes[sub] = deviation_classes.get(sub, 0) + 1

            current += timedelta(days=1)

        # Find clustering in deviation hours
        if deviation_hours:
            from collections import Counter
            hour_counts = Counter(deviation_hours)
            top_hours = [h for h, _ in hour_counts.most_common(3)]
        else:
            top_hours = []

        top_triggers = sorted(deviation_classes, key=deviation_classes.get, reverse=True)[:3]

        detected = len(low_discipline_days) > (lookback_days * 0.25)  # >25% bad days

        if detected and top_hours:
            desc = (
                f"Procrastination detected on {len(low_discipline_days)} of "
                f"{lookback_days} days. Typically occurs around "
                f"{', '.join(f'{h}:00' for h in top_hours)}."
            )
        elif detected:
            desc = f"Low discipline on {len(low_discipline_days)} of {lookback_days} days."
        else:
            desc = "No significant procrastination pattern detected."

        return ProcrastinationPattern(
            detected=detected,
            typical_hours=top_hours,
            avg_recovery_days=2.0,  # TODO: compute from gap between bad→good days
            trigger_classes=top_triggers,
            description=desc,
        )

    # ------------------------------------------------------------------
    # BURNOUT SIGNAL DETECTION
    # ------------------------------------------------------------------

    async def detect_burnout_signal(
        self, lookback_days: int = 14
    ) -> BurnoutSignal:
        """
        Detects burnout signals from recent trend data.

        Burnout indicators:
        1. Discipline declining 3+ consecutive days
        2. PS hours declining 5+ consecutive days
        3. Aura < 1.0 for 7+ days straight
        4. Alertness declining while discipline stays high
           (high effort, low focus = exhaustion signal)
        """
        records = await analytics_repo.get_latest(lookback_days)
        if len(records) < 5:
            return BurnoutSignal(
                detected=False,
                severity="none",
                contributing_factors=[],
                recommendation="Not enough data to assess burnout.",
            )

        factors = []

        # Signal 1: Consecutive discipline decline
        disc_values = [r.discipline for r in records]
        consecutive_decline = self._count_consecutive_decline(disc_values[-5:])
        if consecutive_decline >= 3:
            factors.append(f"Discipline declining for {consecutive_decline} consecutive days")

        # Signal 2: Consecutive PS hours decline
        ps_values = [r.ps_hrs for r in records]
        ps_decline = self._count_consecutive_decline(ps_values[-7:])
        if ps_decline >= 5:
            factors.append(f"Problem-solving hours declining for {ps_decline} days")

        # Signal 3: Sustained low aura (only if we have at least 7 active days of data)
        active_records = [r for r in records if r.tasks_total > 0]
        if len(active_records) >= 7:
            low_aura_streak = sum(1 for r in active_records[-7:] if r.aura < 1.0)
            if low_aura_streak >= 7:
                factors.append("Aura below 1.0 for 7+ consecutive days")

        # Signal 4: High discipline, low alertness (exhaustion pattern)
        recent = records[-5:]
        avg_disc = sum(r.discipline for r in recent) / len(recent)
        avg_alert = sum(r.alertness for r in recent) / len(recent)
        if avg_disc > 70 and avg_alert < 30:
            factors.append("High effort but low focus — possible mental exhaustion")

        # Determine severity
        if len(factors) == 0:
            severity = "none"
            recommendation = "All systems green. Keep the momentum."
        elif len(factors) == 1:
            severity = "mild"
            recommendation = "Early warning signs. Consider lighter tasks tomorrow."
        elif len(factors) == 2:
            severity = "moderate"
            recommendation = "Take a structured break. 1-2 lighter days recommended."
        else:
            severity = "severe"
            recommendation = "Strong burnout signal. A genuine rest day is needed."

        return BurnoutSignal(
            detected=len(factors) > 0,
            severity=severity,
            contributing_factors=factors,
            recommendation=recommendation,
        )

    # ------------------------------------------------------------------
    # WEEKLY SUMMARY
    # ------------------------------------------------------------------

    async def get_weekly_summary(
        self, week_start: Optional[date] = None
    ) -> WeeklyInsight:
        """
        Compute a full weekly performance summary.
        Defaults to the most recent full week (Mon–Sun).
        """
        if week_start is None:
            today = date.today()
            # Go back to last Monday
            week_start = today - timedelta(days=today.weekday())

        week_end = week_start + timedelta(days=6)
        records = await analytics_repo.get_metrics_for_range(week_start, week_end)

        if not records:
            return WeeklyInsight(
                week_start=week_start,
                avg_discipline=0.0,
                avg_alertness=0.0,
                total_ps_hrs=0.0,
                avg_aura=0.0,
                best_day=None,
                worst_day=None,
                streak_delta=0,
            )

        n = len(records)
        avg_discipline = sum(r.discipline for r in records) / n
        avg_alertness = sum(r.alertness for r in records) / n
        total_ps_hrs = sum(r.ps_hrs for r in records)
        avg_aura = sum(r.aura for r in records) / n

        best_day = max(records, key=lambda r: r.discipline).date
        worst_day = min(records, key=lambda r: r.discipline).date

        streak_delta = records[-1].retention_streak - records[0].retention_streak

        return WeeklyInsight(
            week_start=week_start,
            avg_discipline=round(avg_discipline, 2),
            avg_alertness=round(avg_alertness, 2),
            total_ps_hrs=round(total_ps_hrs, 2),
            avg_aura=round(avg_aura, 2),
            best_day=best_day,
            worst_day=worst_day,
            streak_delta=streak_delta,
        )

    # ------------------------------------------------------------------
    # PERCENTILE RANKING
    # ------------------------------------------------------------------

    async def get_percentile(self, metric: str, value: float) -> float:
        """
        Returns what percentile the given value is in,
        relative to all historical records for that metric.
        """
        records = await analytics_repo.get_metrics_for_range(
            date(2024, 1, 1), date.today()
        )
        if not records:
            return 0.0

        all_values = sorted(getattr(r, metric, 0.0) for r in records)
        rank = sum(1 for v in all_values if v <= value)
        return round((rank / len(all_values)) * 100, 1)

    # ------------------------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _count_consecutive_decline(values: list[float]) -> int:
        """Count how many consecutive steps show decline at the end of the list."""
        if len(values) < 2:
            return 0
        count = 0
        for i in range(len(values) - 1, 0, -1):
            if values[i] < values[i - 1]:
                count += 1
            else:
                break
        return count

    # ------------------------------------------------------------------
    # COMPUTE ALL METRIC TRENDS (for analytics router)
    # ------------------------------------------------------------------

    async def compute_metric_trends(
        self, lookback_days: int = 7
    ) -> dict[str, "TrendResult"]:
        """
        Compute direction and average for all major metrics.
        Returns a dict of metric_name → TrendResult.
        """
        metrics = ["discipline", "alertness", "aura", "ps_hrs", "total_points", "retention_streak"]
        results = {}
        for metric in metrics:
            trend_points = await self.get_metric_trend(metric, days=lookback_days)
            direction = await self.get_trend_direction(metric, days=lookback_days)
            values = [p.value for p in trend_points]
            avg = round(sum(values) / len(values), 2) if values else 0.0
            delta = round(values[-1] - values[0], 2) if len(values) >= 2 else 0.0
            results[metric] = TrendResult(direction=direction, avg=avg, delta=delta)
        return results

    async def get_percentile_for_date(
        self, target_date: date, lookback_days: int = 30
    ) -> dict[str, float]:
        """
        Return discipline and aura percentile for a specific date
        compared against the past N days.
        """
        target_metrics = await analytics_repo.get_metrics_for_date(target_date)
        if not target_metrics:
            return {"discipline_pct": 0.0, "aura_pct": 0.0, "has_data": False}

        disc_pct = await self.get_percentile("discipline", target_metrics.discipline)
        aura_pct = await self.get_percentile("aura", target_metrics.aura)

        return {
            "date": target_date.isoformat(),
            "discipline": target_metrics.discipline,
            "discipline_pct": disc_pct,
            "aura": target_metrics.aura,
            "aura_pct": aura_pct,
            "has_data": True,
        }

    async def get_7day_summary_with_best_worst(self) -> dict:
        """Extended 7-day summary including best/worst day names."""
        records = await analytics_repo.get_latest(7)
        if not records:
            return {"avg_discipline": 0.0, "avg_alertness": 0.0,
                    "total_ps_hrs": 0.0, "avg_aura": 0.0,
                    "best_day": None, "worst_day": None, "days_counted": 0}

        n = len(records)
        best = max(records, key=lambda r: r.discipline)
        worst = min(records, key=lambda r: r.discipline)

        return {
            "avg_discipline": round(sum(r.discipline for r in records) / n, 2),
            "avg_alertness": round(sum(r.alertness for r in records) / n, 2),
            "total_ps_hrs": round(sum(r.ps_hrs for r in records), 2),
            "avg_aura": round(sum(r.aura for r in records) / n, 3),
            "best_day": best.date.strftime("%A"),
            "worst_day": worst.date.strftime("%A"),
            "days_counted": n,
        }


@dataclass
class TrendResult:
    """Compact result for a single metric's trend."""
    direction: str   # "improving" | "declining" | "stable"
    avg: float
    delta: float     # Last value minus first value


# Singleton
trend_analyzer = TrendAnalyzer()

