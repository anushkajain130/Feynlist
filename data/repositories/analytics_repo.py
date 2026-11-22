"""
Analytics Repository
====================
All database operations for daily_analytics and hourly_points tables.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from loguru import logger

from core.models import DailyMetrics, HourlyPoint
from data.database import db
from core import clock


class AnalyticsRepository:
    """CRUD for daily_analytics and hourly_points tables."""

    # ------------------------------------------------------------------
    # DailyMetrics
    # ------------------------------------------------------------------

    async def get_metrics_for_date(self, target_date: date) -> Optional[DailyMetrics]:
        """Fetch analytics for a specific date. Returns None if no data."""
        row = await db.fetch_one(
            "SELECT * FROM daily_analytics WHERE date = ?",
            (target_date.isoformat(),),
        )
        return self._row_to_metrics(row) if row else None

    async def get_metrics_for_range(
        self, start: date, end: date
    ) -> list[DailyMetrics]:
        """Fetch analytics for a date range, ordered chronologically."""
        rows = await db.fetch_all(
            """
            SELECT * FROM daily_analytics
            WHERE date BETWEEN ? AND ?
            ORDER BY date ASC
            """,
            (start.isoformat(), end.isoformat()),
        )
        return [self._row_to_metrics(r) for r in rows]

    async def get_latest(self, n: int = 7) -> list[DailyMetrics]:
        """Fetch the n most recent analytics records."""
        rows = await db.fetch_all(
            "SELECT * FROM daily_analytics ORDER BY date DESC LIMIT ?",
            (n,),
        )
        return [self._row_to_metrics(r) for r in reversed(rows)]

    async def get_yesterday_metrics(self) -> Optional[DailyMetrics]:
        """Convenience: fetch yesterday's analytics for EWM weighting."""
        from datetime import timedelta
        yesterday = clock.today() - timedelta(days=1)
        return await self.get_metrics_for_date(yesterday)

    async def upsert_metrics(self, metrics: DailyMetrics) -> None:
        """Insert or update analytics for a date."""
        async with db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO daily_analytics (
                    date, alertness, discipline, ps_hrs, aura,
                    retention_streak, happiness, total_points,
                    tasks_completed, tasks_total, relapsed, commitment_kept, computed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                ON CONFLICT(date) DO UPDATE SET
                    alertness        = excluded.alertness,
                    discipline       = excluded.discipline,
                    ps_hrs           = excluded.ps_hrs,
                    aura             = excluded.aura,
                    retention_streak = excluded.retention_streak,
                    happiness        = excluded.happiness,
                    total_points     = excluded.total_points,
                    tasks_completed  = excluded.tasks_completed,
                    tasks_total      = excluded.tasks_total,
                    relapsed         = excluded.relapsed,
                    commitment_kept  = excluded.commitment_kept,
                    computed_at      = datetime('now')
                """,
                (
                    metrics.date.isoformat(),
                    round(metrics.alertness, 4),
                    round(metrics.discipline, 4),
                    round(metrics.ps_hrs, 4),
                    round(metrics.aura, 4),
                    metrics.retention_streak,
                    round(metrics.happiness, 4),
                    metrics.total_points,
                    metrics.tasks_completed,
                    metrics.tasks_total,
                    int(metrics.commitment_kept is False),  # legacy column, kept for compatibility
                    None if metrics.commitment_kept is None else int(metrics.commitment_kept),
                ),
            )
            await conn.commit()
        logger.debug(f"Upserted analytics for {metrics.date}: aura={metrics.aura:.2f}")

    async def get_streak(self) -> int:
        """
        Get the current consistency streak.
        Returns the streak from the most recent analytics record.
        """
        row = await db.fetch_one(
            "SELECT retention_streak FROM daily_analytics ORDER BY date DESC LIMIT 1"
        )
        return row["retention_streak"] if row else 0

    async def get_all_dates(self) -> list[date]:
        """Return all dates that have analytics records."""
        rows = await db.fetch_all(
            "SELECT date FROM daily_analytics ORDER BY date ASC"
        )
        return [date.fromisoformat(r["date"]) for r in rows]

    # ------------------------------------------------------------------
    # HourlyPoints
    # ------------------------------------------------------------------

    async def get_hourly_for_date(self, target_date: date) -> list[HourlyPoint]:
        """Fetch the 24-hour point distribution for a date."""
        rows = await db.fetch_all(
            "SELECT * FROM hourly_points WHERE date = ? ORDER BY hour ASC",
            (target_date.isoformat(),),
        )
        return [HourlyPoint(date=target_date, hour=r["hour"], points=r["points"]) for r in rows]

    async def log_hourly_point(self, target_date: date, hour: int, points: int) -> None:
        """
        Add points to a specific hour.
        Accumulates — does NOT replace existing value.
        """
        async with db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO hourly_points (date, hour, points)
                VALUES (?, ?, ?)
                ON CONFLICT(date, hour) DO UPDATE SET
                    points = hourly_points.points + excluded.points
                """,
                (target_date.isoformat(), hour, points),
            )
            await conn.commit()

    async def get_best_productive_hours(self, lookback_days: int = 30) -> list[int]:
        """
        Returns hours of the day (0–23) ranked by average points,
        useful for identifying peak productivity windows.
        """
        from datetime import timedelta
        cutoff = (clock.today() - timedelta(days=lookback_days)).isoformat()
        rows = await db.fetch_all(
            """
            SELECT hour, AVG(points) as avg_pts
            FROM hourly_points
            WHERE date >= ?
            GROUP BY hour
            ORDER BY avg_pts DESC
            """,
            (cutoff,),
        )
        return [r["hour"] for r in rows]

    # ------------------------------------------------------------------
    # PRIVATE
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_metrics(row) -> DailyMetrics:
        d = dict(row)
        return DailyMetrics(
            date=date.fromisoformat(d["date"]),
            alertness=d.get("alertness", 0.0),
            discipline=d.get("discipline", 0.0),
            ps_hrs=d.get("ps_hrs", 0.0),
            aura=d.get("aura", 0.0),
            retention_streak=d.get("retention_streak", 0),
            happiness=d.get("happiness", 0.0),
            total_points=d.get("total_points", 0),
            tasks_completed=d.get("tasks_completed", 0),
            tasks_total=d.get("tasks_total", 0),
            commitment_kept=_commitment_from_row(d),
        )


def _commitment_from_row(d: dict) -> Optional[bool]:
    """Read the check-in answer; legacy rows only have `relapsed`."""
    kept = d.get("commitment_kept")
    if kept is not None:
        return bool(kept)
    if d.get("relapsed"):
        return False
    return None


# Singleton
analytics_repo = AnalyticsRepository()
