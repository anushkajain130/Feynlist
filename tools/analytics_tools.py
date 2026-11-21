"""
Analytics Tools
===============
Tools for agents to read current performance metrics and trends.

Available tools:
  - get_daily_metrics    : Full DailyMetrics for a specific date
  - get_trend_summary    : 7-day trend direction for all metrics
  - get_percentile       : How today's score compares to historical data
  - get_burnout_signal   : Current burnout risk assessment
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field

from core.exceptions import ToolExecutionError
from data.repositories.analytics_repo import analytics_repo
from analytics.trends import trend_analyzer
from tools.base_tool import BaseTool, ToolContext
from core import clock


# =============================================================================
# GET DAILY METRICS
# =============================================================================

class GetDailyMetricsInput(BaseModel):
    target_date: Optional[str] = Field(
        default=None,
        description="ISO date YYYY-MM-DD. Defaults to today."
    )


class GetDailyMetricsOutput(BaseModel):
    date: str
    alertness: float
    discipline: float
    ps_hrs: float
    aura: float
    retention_streak: int
    total_points: int
    completion_rate: float
    has_data: bool


class GetDailyMetricsTool(BaseTool):
    name = "get_daily_metrics"
    description = (
        "Returns today's (or any date's) performance metrics: "
        "alertness, discipline, problem-solving hours, aura score, "
        "and retention streak. Use this to understand how the user is performing."
    )
    input_schema = GetDailyMetricsInput
    output_schema = GetDailyMetricsOutput

    async def execute(
        self, input: GetDailyMetricsInput, context: ToolContext
    ) -> GetDailyMetricsOutput:
        try:
            target = (
                date.fromisoformat(input.target_date)
                if input.target_date
                else clock.today()
            )
            metrics = await analytics_repo.get_metrics_for_date(target)
        except Exception as e:
            raise ToolExecutionError(f"Failed to load metrics: {e}") from e

        if not metrics:
            return GetDailyMetricsOutput(
                date=target.isoformat(),
                alertness=0.0, discipline=0.0, ps_hrs=0.0,
                aura=0.0, retention_streak=0, total_points=0,
                completion_rate=0.0, has_data=False,
            )

        return GetDailyMetricsOutput(
            date=metrics.date.isoformat(),
            alertness=metrics.alertness,
            discipline=metrics.discipline,
            ps_hrs=metrics.ps_hrs,
            aura=metrics.aura,
            retention_streak=metrics.retention_streak,
            total_points=metrics.total_points,
            completion_rate=metrics.completion_rate,
            has_data=True,
        )


# =============================================================================
# GET TREND SUMMARY
# =============================================================================

class GetTrendSummaryInput(BaseModel):
    days: int = Field(default=7, description="Lookback window in days.")


class GetTrendSummaryOutput(BaseModel):
    discipline_direction: str    # "improving", "declining", "stable"
    alertness_direction: str
    ps_hrs_direction: str
    aura_direction: str
    avg_7day: dict               # Quick averages
    consistency_score: float     # 0–100
    summary_text: str            # Human-readable one-liner


class GetTrendSummaryTool(BaseTool):
    name = "get_trend_summary"
    description = (
        "Returns trend directions (improving/declining/stable) for all key metrics "
        "over the last N days, plus a consistency score. Use this to understand "
        "the user's momentum and tailor your response tone accordingly."
    )
    input_schema = GetTrendSummaryInput
    output_schema = GetTrendSummaryOutput

    async def execute(
        self, input: GetTrendSummaryInput, context: ToolContext
    ) -> GetTrendSummaryOutput:
        try:
            disc_dir = await trend_analyzer.get_trend_direction("discipline", input.days)
            alert_dir = await trend_analyzer.get_trend_direction("alertness", input.days)
            ps_dir = await trend_analyzer.get_trend_direction("ps_hrs", input.days)
            aura_dir = await trend_analyzer.get_trend_direction("aura", input.days)
            avg_7day = await trend_analyzer.get_7day_summary()
            consistency = await trend_analyzer.get_consistency_score(input.days)
        except Exception as e:
            raise ToolExecutionError(f"Failed to compute trends: {e}") from e

        # Build human-readable summary
        directions = [disc_dir, alert_dir, ps_dir, aura_dir]
        improving_count = directions.count("improving")
        declining_count = directions.count("declining")

        if improving_count >= 3:
            summary_text = "Strong upward momentum across metrics."
        elif declining_count >= 3:
            summary_text = "Multiple metrics declining — user may need support."
        elif disc_dir == "improving":
            summary_text = "Discipline is trending up — good momentum."
        elif disc_dir == "declining":
            summary_text = "Discipline trending down — intervention may help."
        else:
            summary_text = f"Mixed trends. Consistency score: {consistency:.0f}/100."

        return GetTrendSummaryOutput(
            discipline_direction=disc_dir,
            alertness_direction=alert_dir,
            ps_hrs_direction=ps_dir,
            aura_direction=aura_dir,
            avg_7day=avg_7day,
            consistency_score=consistency,
            summary_text=summary_text,
        )


# =============================================================================
# GET PERCENTILE
# =============================================================================

class GetPercentileInput(BaseModel):
    metric: str = Field(
        description="Metric name: 'discipline', 'alertness', 'ps_hrs', 'aura'"
    )
    value: Optional[float] = Field(
        default=None,
        description="Value to rank. Defaults to today's value for the metric."
    )


class GetPercentileOutput(BaseModel):
    metric: str
    value: float
    percentile: Optional[float]  # None when there isn't enough history
    interpretation: str


class GetPercentileTool(BaseTool):
    name = "get_percentile"
    description = (
        "Returns what percentile today's score is, relative to the user's own history. "
        "Needs at least 14 days of history; otherwise it says so and you must not "
        "make any comparison to past days."
    )
    input_schema = GetPercentileInput
    output_schema = GetPercentileOutput

    async def execute(
        self, input: GetPercentileInput, context: ToolContext
    ) -> GetPercentileOutput:
        try:
            value = input.value
            if value is None:
                today_metrics = await analytics_repo.get_metrics_for_date(clock.today())
                if today_metrics:
                    value = getattr(today_metrics, input.metric, 0.0)
                else:
                    value = 0.0

            percentile = await trend_analyzer.get_percentile(input.metric, value)
        except Exception as e:
            raise ToolExecutionError(f"Failed to compute percentile: {e}") from e

        if percentile is None:
            interpretation = (
                f"Not enough history yet (needs {trend_analyzer.MIN_DAYS_FOR_PERCENTILE} days). "
                "Don't compare today to past days."
            )
        elif percentile >= 90:
            interpretation = f"Exceptional. Top {100 - percentile:.0f}% of all your days."
        elif percentile >= 75:
            interpretation = f"Strong day. Better than {percentile:.0f}% of your history."
        elif percentile >= 50:
            interpretation = f"Above your median. {percentile:.0f}th percentile."
        elif percentile >= 25:
            interpretation = f"Below your median. Room to grow today."
        else:
            interpretation = f"Tough day. Bottom {percentile:.0f}% historically."

        return GetPercentileOutput(
            metric=input.metric,
            value=value,
            percentile=percentile,
            interpretation=interpretation,
        )


# =============================================================================
# GET BURNOUT SIGNAL
# =============================================================================

class GetBurnoutSignalInput(BaseModel):
    lookback_days: int = Field(default=14, description="Days to look back.")


class GetBurnoutSignalOutput(BaseModel):
    detected: bool
    severity: str
    factors: list[str]
    recommendation: str


class GetBurnoutSignalTool(BaseTool):
    name = "get_burnout_signal"
    description = (
        "Detects burnout signals from recent performance trends. "
        "Returns severity (none/mild/moderate/severe) and specific contributing factors. "
        "Use this before delivering hard feedback — if burnout is detected, "
        "soften your tone and prioritize recovery over performance."
    )
    input_schema = GetBurnoutSignalInput
    output_schema = GetBurnoutSignalOutput

    async def execute(
        self, input: GetBurnoutSignalInput, context: ToolContext
    ) -> GetBurnoutSignalOutput:
        try:
            signal = await trend_analyzer.detect_burnout_signal(input.lookback_days)
        except Exception as e:
            raise ToolExecutionError(f"Failed to compute burnout signal: {e}") from e

        return GetBurnoutSignalOutput(
            detected=signal.detected,
            severity=signal.severity,
            factors=signal.contributing_factors,
            recommendation=signal.recommendation,
        )
