"""
Time Tools
==========
Tools giving agents awareness of time, schedule position, and day context.

Available tools:
  - get_time_context    : Current time, day progress, time until next task
  - get_schedule_window : Look at a specific time window in the schedule
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from pydantic import BaseModel, Field

from core.exceptions import ToolExecutionError
from data.repositories.task_repo import task_repo
from tools.base_tool import BaseTool, ToolContext
from core import clock


# =============================================================================
# GET TIME CONTEXT
# =============================================================================

class GetTimeContextInput(BaseModel):
    pass  # No input needed — always returns current state


class GetTimeContextOutput(BaseModel):
    current_time: str          # "HH:MM"
    current_date: str          # "YYYY-MM-DD"
    day_of_week: str           # "Monday"
    minutes_until_midnight: int
    day_progress_pct: float    # How far through the day (6am=0%, midnight=100%)
    current_task_name: Optional[str]
    minutes_until_next_task: Optional[int]
    next_task_name: Optional[str]
    is_work_hour: bool         # Between 6am and 10pm


class GetTimeContextTool(BaseTool):
    name = "get_time_context"
    description = (
        "Returns the current time, day progress, the currently active task, "
        "and time until the next task. Use this to ground your response in "
        "the user's actual moment — avoid generic responses that ignore time of day."
    )
    input_schema = GetTimeContextInput
    output_schema = GetTimeContextOutput

    async def execute(
        self, input: GetTimeContextInput, context: ToolContext
    ) -> GetTimeContextOutput:
        now = clock.now()
        today = now.date()
        now_time = now.time()

        try:
            tasks = await task_repo.get_tasks_for_date(today)
        except Exception as e:
            raise ToolExecutionError(f"Failed to load tasks: {e}") from e

        # Current and next task
        current_task = None
        next_task = None
        minutes_until_next = None

        for task in sorted(tasks, key=lambda t: t.start_time):
            if task.is_active_at(now_time):
                current_task = task
            elif task.start_time_obj > now_time and next_task is None:
                next_task = task
                # Minutes until next task starts
                next_dt = datetime.combine(today, task.start_time_obj)
                minutes_until_next = int((next_dt - now).total_seconds() / 60)

        # Day progress (6am = 0%, midnight = 100%)
        day_start = datetime.combine(today, datetime.min.time().replace(hour=6))
        day_end = datetime.combine(today + timedelta(days=1), datetime.min.time())
        day_total = (day_end - day_start).total_seconds()
        elapsed = max(0, (now - day_start).total_seconds())
        day_progress = min(100.0, (elapsed / day_total) * 100)

        # Minutes until midnight
        midnight = datetime.combine(today + timedelta(days=1), datetime.min.time())
        minutes_until_midnight = int((midnight - now).total_seconds() / 60)

        return GetTimeContextOutput(
            current_time=now.strftime("%H:%M"),
            current_date=today.isoformat(),
            day_of_week=now.strftime("%A"),
            minutes_until_midnight=minutes_until_midnight,
            day_progress_pct=round(day_progress, 1),
            current_task_name=current_task.task if current_task else None,
            minutes_until_next_task=minutes_until_next,
            next_task_name=next_task.task if next_task else None,
            is_work_hour=6 <= now.hour < 22,
        )
