"""
Analytics Router
================
All analytics/metrics endpoints.

GET  /api/analytics/today              — today's live metrics
GET  /api/analytics/history?days=7     — last N days of metrics
GET  /api/analytics/trends/{metric}    — trend direction for a metric
GET  /api/analytics/summary/week       — weekly summary
GET  /api/analytics/burnout            — current burnout signal
GET  /api/analytics/percentile/{date}  — user's percentile on a given day
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.schemas import (
    DailyMetricsResponse, TrendResponse,
    WeeklySummaryResponse, BurnoutSignalResponse,
    CheckInRequest,
)
from data.repositories.analytics_repo import analytics_repo
from analytics.trends import trend_analyzer
from core.exceptions import DatabaseError

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


def _metrics_response(m, has_data: bool = True) -> DailyMetricsResponse:
    return DailyMetricsResponse(
        date=m.date.isoformat(),
        alertness=round(m.alertness, 2),
        discipline=round(m.discipline, 2),
        ps_hrs=round(m.ps_hrs, 2),
        aura=round(m.aura, 3),
        retention_streak=m.retention_streak,
        total_points=m.total_points,
        tasks_completed=m.tasks_completed,
        tasks_total=m.tasks_total,
        completion_rate=round(m.completion_rate, 1),
        has_data=has_data,
        relapsed=m.relapsed,
    )


@router.get("/today", response_model=DailyMetricsResponse)
async def get_today_metrics():
    """Return live metrics for today. Returns empty model if pipeline hasn't run."""
    from analytics.pipeline import pipeline
    # Run pipeline to ensure metrics are fresh
    metrics = await pipeline.run(date.today())
    return _metrics_response(metrics)


@router.get("/history", response_model=list[DailyMetricsResponse])
async def get_history(days: int = Query(default=7, ge=1, le=90)):
    """Return daily metrics for the last N days."""
    today = date.today()
    results = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        m = await analytics_repo.get_metrics_for_date(d)
        if m:
            results.append(_metrics_response(m))
    return results


@router.get("/trends/{metric}", response_model=TrendResponse)
async def get_trend(
    metric: str,
    days: int = Query(default=7, ge=3, le=30),
):
    """
    Return the trend direction and data for a specific metric.
    Valid metrics: discipline, alertness, aura, ps_hrs, total_points
    """
    valid = {"discipline", "alertness", "aura", "ps_hrs", "total_points"}
    if metric not in valid:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown metric '{metric}'. Valid: {sorted(valid)}"
        )

    trends = await trend_analyzer.compute_metric_trends(lookback_days=days)
    trend = trends.get(metric)
    if not trend:
        raise HTTPException(status_code=404, detail=f"No trend data for '{metric}'")

    # Build data points from history
    today = date.today()
    data_points = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        m = await analytics_repo.get_metrics_for_date(d)
        if m:
            data_points.append({
                "date": d.isoformat(),
                "value": round(getattr(m, metric, 0), 2),
            })

    return TrendResponse(
        metric=metric,
        direction=trend.direction.value,
        data_points=data_points,
        avg_7day=round(trend.avg, 2),
    )


@router.get("/summary/week", response_model=WeeklySummaryResponse)
async def get_weekly_summary():
    """Return aggregated summary for the past 7 days."""
    summary = await trend_analyzer.get_7day_summary_with_best_worst()
    trends = await trend_analyzer.compute_metric_trends()
    streak_trend = trends.get("retention_streak")

    return WeeklySummaryResponse(
        week_start=(date.today() - timedelta(days=6)).isoformat(),
        avg_discipline=round(summary.get("avg_discipline", 0), 1),
        avg_alertness=round(summary.get("avg_alertness", 0), 1),
        total_ps_hrs=round(summary.get("total_ps_hrs", 0), 1),
        avg_aura=round(summary.get("avg_aura", 0), 3),
        best_day=summary.get("best_day"),
        worst_day=summary.get("worst_day"),
        streak_delta=int(streak_trend.delta) if streak_trend else 0,
    )


@router.get("/burnout", response_model=BurnoutSignalResponse)
async def get_burnout_signal():
    """Return current burnout signal based on last 14 days of data."""
    signal = await trend_analyzer.detect_burnout_signal(lookback_days=14)
    return BurnoutSignalResponse(
        detected=signal.detected,
        severity=signal.severity,
        factors=signal.contributing_factors,
        recommendation=signal.recommendation,
    )


@router.get("/percentile/{target_date}", response_model=dict)
async def get_percentile(target_date: str):
    """
    Return the user's discipline and aura percentile for a specific date
    compared to the past 30 days.
    """
    try:
        d = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date: {target_date}")

    percentiles = await trend_analyzer.get_percentile_for_date(d, lookback_days=30)
    return percentiles


@router.post("/check-in", response_model=DailyMetricsResponse)
async def check_in(req: CheckInRequest):
    """
    Log private daily check-in relapse status.
    Recalculates the streak and metrics immediately.
    """
    from datetime import date
    from analytics.pipeline import pipeline
    from data.repositories.task_repo import task_repo
    from core.models import DailyMetrics
    
    try:
        target_date = date.fromisoformat(req.date) if req.date else date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    try:
        # Load existing daily metrics or construct a blank one
        metrics = await analytics_repo.get_metrics_for_date(target_date)
        if not metrics:
            tasks = await task_repo.get_tasks_for_date(target_date)
            metrics = DailyMetrics(
                date=target_date,
                tasks_total=len(tasks),
            )
            
        metrics.relapsed = req.relapsed
        await analytics_repo.upsert_metrics(metrics)
        
        # Trigger full pipeline recalculation to update streak & aura correctly
        updated_metrics = await pipeline.run(target_date)
        return _metrics_response(updated_metrics)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Check-in failed: {e}")
