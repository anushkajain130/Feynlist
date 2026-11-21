"""
Notification Triggers
======================
Functions that emit AppEvents to the event bus based on real-world conditions.
These are the "sensors" — they detect what's happening and publish the right event.

Called by the scheduler on a timer, or directly from the GUI on state changes.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from loguru import logger

from core.models import AppEvent, EventType
from events.event_bus import event_bus
from data.repositories.task_repo import task_repo
from data.repositories.analytics_repo import analytics_repo
from analytics.trends import trend_analyzer
from core import clock


async def emit_task_missed() -> None:
    """
    Check if any task passed its end time without being completed.
    Fires TASK_MISSED event for each missed task found.
    """
    now = clock.now().time()
    today = clock.today()

    try:
        tasks = await task_repo.get_tasks_for_date(today)
    except Exception as e:
        logger.error(f"Trigger: failed to load tasks: {e}")
        return

    for task in tasks:
        if task.is_past_at(now) and not task.completed:
            # Skip passive classes — no point alerting for sleep/break misses
            if task.task_class.value in ("Sleep", "Break", "Deviated", "revived"):
                continue

            event = AppEvent(
                event_type=EventType.TASK_MISSED,
                source="scheduler",
                payload={
                    "task_id": task.id,
                    "task_name": task.task,
                    "end_time": task.end_time,
                    "points": task.points,
                    "class": task.task_class.value,
                    "message": f"Task missed: '{task.task}' ended at {task.end_time}.",
                },
            )
            logger.info(f"Trigger: TASK_MISSED → {task.task}")
            await event_bus.publish(event)


async def emit_scheduled_checkin() -> None:
    """
    Fire a periodic performance checkin event.
    ZeroTwo reviews the current metrics by default.
    """
    today_metrics = await analytics_repo.get_metrics_for_date(clock.today())
    summary = await trend_analyzer.get_7day_summary()

    event = AppEvent(
        event_type=EventType.SCHEDULED_CHECKIN,
        source="scheduler",
        payload={
            "message": "Scheduled performance check-in.",
            "today_discipline": today_metrics.discipline if today_metrics else 0.0,
            "today_aura": today_metrics.aura if today_metrics else 0.0,
            "week_avg_discipline": summary.get("avg_discipline", 0.0),
        },
    )
    logger.info("Trigger: SCHEDULED_CHECKIN emitted.")
    await event_bus.publish(event)


async def emit_burnout_check() -> None:
    """
    Run burnout detection and emit BURNOUT_DETECTED if triggered.
    Fires at end of day or when called manually.
    """
    signal = await trend_analyzer.detect_burnout_signal(lookback_days=14)

    if signal.detected:
        event = AppEvent(
            event_type=EventType.BURNOUT_DETECTED,
            source="scheduler",
            payload={
                "severity": signal.severity,
                "factors": signal.contributing_factors,
                "recommendation": signal.recommendation,
                "message": f"Burnout signal ({signal.severity}): {signal.recommendation}",
            },
        )
        logger.warning(f"Trigger: BURNOUT_DETECTED severity={signal.severity}")
        await event_bus.publish(event)


async def emit_streak_event() -> None:
    """
    Emit STREAK_BROKEN or STREAK_MILESTONE based on today's metrics.
    """
    today = await analytics_repo.get_metrics_for_date(clock.today())
    yesterday = await analytics_repo.get_metrics_for_date(
        clock.today() - timedelta(days=1)
    )

    if not today or not yesterday:
        return

    # Streak broken today
    if yesterday.retention_streak > 0 and today.retention_streak == 0:
        event = AppEvent(
            event_type=EventType.STREAK_BROKEN,
            source="scheduler",
            payload={
                "previous_streak": yesterday.retention_streak,
                "message": f"Streak of {yesterday.retention_streak} days broken.",
            },
        )
        logger.warning(f"Trigger: STREAK_BROKEN after {yesterday.retention_streak}d")
        await event_bus.publish(event)

    # Milestone: 7, 14, 30, 60, 90 days
    milestones = {7, 14, 30, 60, 90}
    if today.retention_streak in milestones:
        event = AppEvent(
            event_type=EventType.STREAK_MILESTONE,
            source="scheduler",
            payload={
                "streak": today.retention_streak,
                "message": f"{today.retention_streak}-day streak milestone!",
            },
        )
        logger.info(f"Trigger: STREAK_MILESTONE {today.retention_streak}d")
        await event_bus.publish(event)


async def emit_day_start() -> None:
    """Fired at the start of each day. Freya reviews the incoming schedule."""
    tasks = await task_repo.get_tasks_for_date(clock.today())
    event = AppEvent(
        event_type=EventType.DAY_START,
        source="scheduler",
        payload={
            "task_count": len(tasks),
            "message": "New day started. Task schedule loaded.",
        },
    )
    logger.info("Trigger: DAY_START emitted.")
    await event_bus.publish(event)


async def emit_day_end() -> None:
    """Fired at end of day. Anya does the review, analytics pipeline runs."""
    from analytics.pipeline import pipeline
    metrics = await pipeline.run(clock.today())

    event = AppEvent(
        event_type=EventType.DAY_END_REVIEW,
        source="scheduler",
        payload={
            "discipline": metrics.discipline,
            "aura": metrics.aura,
            "streak": metrics.retention_streak,
            "pts": metrics.total_points,
            "message": f"Day ended. discipline={metrics.discipline:.1f}% aura={metrics.aura:.2f}",
        },
    )
    logger.info("Trigger: DAY_END_REVIEW emitted.")
    await event_bus.publish(event)

    # Also check burnout and streak
    await emit_burnout_check()
    await emit_streak_event()


async def emit_task_completed(task) -> None:
    """Fired when a task becomes fully completed. Albedo celebrates."""
    event = AppEvent(
        event_type=EventType.TASK_COMPLETED,
        source="tasks",
        payload={
            "task_id": task.id,
            "task_name": task.task,
            "start_time": task.start_time,
            "end_time": task.end_time,
            "message": f"Task completed: '{task.task}' ({task.start_time}–{task.end_time}).",
        },
    )
    logger.info(f"Trigger: TASK_COMPLETED for '{task.task}'")
    await event_bus.publish(event)


def fire_and_forget(coro) -> None:
    """Run an event emitter in the background so API responses aren't delayed by an LLM call."""
    import asyncio
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


_background: set = set()


async def emit_user_message(message: str, source: str = "user") -> None:
    """
    Emit a user direct message event.
    Called whenever the user types in the chat panel.
    """
    event = AppEvent(
        event_type=EventType.USER_DIRECT_MESSAGE,
        source=source,
        payload={"message": message},
    )
    await event_bus.publish(event)
