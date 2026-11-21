"""
Task Tools
==========
Tools for reading and modifying tasks.
These are the most commonly called tools by agents.

Available tools:
  - get_current_tasks       : Today's tasks, current + upcoming highlighted
  - get_task_summary        : Compressed task status for context
  - mark_subtask            : Toggle a subtask (agents can mark tasks done)
  - get_missed_tasks        : Tasks that should have been started but weren't
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from core.models import Task, TaskClass
from core.exceptions import ToolExecutionError
from data.repositories.task_repo import task_repo
from tools.base_tool import BaseTool, ToolContext
from analytics.pipeline import pipeline
from core import clock


# =============================================================================
# GET CURRENT TASKS
# =============================================================================

class GetCurrentTasksInput(BaseModel):
    target_date: Optional[str] = Field(
        default=None,
        description="ISO date (YYYY-MM-DD). Defaults to today."
    )
    include_completed: bool = Field(
        default=True,
        description="Whether to include completed tasks in the response."
    )


class GetCurrentTasksOutput(BaseModel):
    date: str
    total_tasks: int
    completed_count: int
    current_task: Optional[dict] = None       # Task active right now
    upcoming_tasks: list[dict] = []           # Next 3 tasks
    past_tasks: list[dict] = []               # Tasks already done or missed
    completion_pct: float = 0.0


class GetCurrentTasksTool(BaseTool):
    name = "get_current_tasks"
    description = (
        "Returns today's task schedule with the currently active task, "
        "upcoming tasks, and completed/past tasks. Use this to understand "
        "where the user is in their day."
    )
    input_schema = GetCurrentTasksInput
    output_schema = GetCurrentTasksOutput

    async def execute(
        self, input: GetCurrentTasksInput, context: ToolContext
    ) -> GetCurrentTasksOutput:
        try:
            target = (
                date.fromisoformat(input.target_date)
                if input.target_date
                else clock.today()
            )
            tasks = await task_repo.get_tasks_for_date(target)
        except Exception as e:
            raise ToolExecutionError(f"Failed to load tasks: {e}") from e

        if not tasks:
            return GetCurrentTasksOutput(
                date=target.isoformat(),
                total_tasks=0,
                completed_count=0,
            )

        now = clock.now().time()
        current_task_obj = None
        upcoming_tasks: list = []
        past_tasks: list = []

        for t in tasks:
            if t.is_active_at(now):
                current_task_obj = t
            elif t.is_past_at(now):
                if input.include_completed or not t.completed:
                    past_tasks.append(t)
            else:
                upcoming_tasks.append(t)

        completed_count = sum(1 for t in tasks if t.completed)
        completion_pct = round(completed_count / len(tasks) * 100, 1)

        return GetCurrentTasksOutput(
            date=target.isoformat(),
            total_tasks=len(tasks),
            completed_count=completed_count,
            current_task=self._task_to_dict(current_task_obj) if current_task_obj else None,
            upcoming_tasks=[self._task_to_dict(t) for t in upcoming_tasks[:3]],
            past_tasks=[self._task_to_dict(t) for t in past_tasks],
            completion_pct=completion_pct,
        )

    @staticmethod
    def _task_to_dict(task: Task) -> dict:
        return {
            "id": task.id,
            "task": task.task,
            "start_time": task.start_time,
            "end_time": task.end_time,
            "points": task.points,
            "completed": task.completed,
            "class": task.task_class.value,
            "start_and_sit": task.start_and_sit,
            "complete_task": task.complete_task,
            "slider_val": task.slider_val,
            "ps_var": task.ps_var,
        }


# =============================================================================
# GET TASK SUMMARY (compressed, for agent context)
# =============================================================================

class GetTaskSummaryInput(BaseModel):
    target_date: Optional[str] = None


class GetTaskSummaryOutput(BaseModel):
    summary: str           # One-paragraph natural language summary
    stats: dict            # Structured stats for quick reference


class GetTaskSummaryTool(BaseTool):
    name = "get_task_summary"
    description = (
        "Returns a compressed natural-language summary of today's task progress. "
        "Use this instead of get_current_tasks when you only need a quick overview "
        "to include in a response (saves context tokens)."
    )
    input_schema = GetTaskSummaryInput
    output_schema = GetTaskSummaryOutput

    async def execute(
        self, input: GetTaskSummaryInput, context: ToolContext
    ) -> GetTaskSummaryOutput:
        try:
            target = (
                date.fromisoformat(input.target_date)
                if input.target_date
                else clock.today()
            )
            tasks = await task_repo.get_tasks_for_date(target)
        except Exception as e:
            raise ToolExecutionError(f"Failed to load tasks: {e}") from e

        if not tasks:
            return GetTaskSummaryOutput(
                summary="No tasks scheduled for today.",
                stats={"total": 0, "completed": 0, "completion_pct": 0},
            )

        now = clock.now().time()
        completed = [t for t in tasks if t.completed]
        past_incomplete = [t for t in tasks if t.is_past_at(now) and not t.completed]
        current = next((t for t in tasks if t.is_active_at(now)), None)
        remaining = [t for t in tasks if not t.is_past_at(now) and not t.is_active_at(now)]
        total_pts = sum(t.points for t in tasks)
        earned_pts = sum(
            int(t.points * 0.5) * int(t.start_and_sit)
            + int(t.points * 0.3) * int(t.complete_task)
            + t.slider_val
            for t in tasks
        )

        current_str = f"Currently on: '{current.task}' ({current.start_time}–{current.end_time})." if current else "No active task right now."
        missed_str = f"{len(past_incomplete)} task(s) missed." if past_incomplete else "No missed tasks."

        summary = (
            f"{len(completed)}/{len(tasks)} tasks completed ({earned_pts}/{total_pts} pts). "
            f"{current_str} "
            f"{len(remaining)} tasks remaining. "
            f"{missed_str}"
        )

        return GetTaskSummaryOutput(
            summary=summary,
            stats={
                "total": len(tasks),
                "completed": len(completed),
                "missed": len(past_incomplete),
                "remaining": len(remaining),
                "completion_pct": round(len(completed) / len(tasks) * 100, 1),
                "pts_earned": earned_pts,
                "pts_total": total_pts,
            },
        )


# =============================================================================
# MARK SUBTASK (agents can toggle subtasks)
# =============================================================================

class MarkSubtaskInput(BaseModel):
    task_id: str = Field(description="The task ID to update.")
    subtask_name: str = Field(
        description="One of: 'Start_and_Sit_for_5_mins', 'Complete_the_task', 'Be_attentive'"
    )
    value: bool = Field(description="True to mark done, False to unmark.")
    slider_val: Optional[int] = Field(
        default=None,
        description="For Be_attentive only: the focus slider value (0 to points*0.2)."
    )


class MarkSubtaskOutput(BaseModel):
    success: bool
    task_id: str
    updated_task: dict


class MarkSubtaskTool(BaseTool):
    name = "mark_subtask"
    description = (
        "Mark a subtask as complete or incomplete on a task. "
        "Use this when the user reports completing a task or you want to "
        "acknowledge a milestone. Triggers analytics recalculation."
    )
    input_schema = MarkSubtaskInput
    output_schema = MarkSubtaskOutput

    async def execute(
        self, input: MarkSubtaskInput, context: ToolContext
    ) -> MarkSubtaskOutput:
        try:
            updated_task = await task_repo.toggle_subtask(
                task_id=input.task_id,
                subtask_name=input.subtask_name,
                value=input.value,
                slider_val=input.slider_val,
            )
            # Trigger analytics recalculation in background
            await pipeline.run(updated_task.date)

            return MarkSubtaskOutput(
                success=True,
                task_id=input.task_id,
                updated_task=GetCurrentTasksTool._task_to_dict(updated_task),
            )
        except Exception as e:
            raise ToolExecutionError(f"Failed to update subtask: {e}") from e


# =============================================================================
# GET MISSED TASKS
# =============================================================================

class GetMissedTasksInput(BaseModel):
    target_date: Optional[str] = None


class GetMissedTasksOutput(BaseModel):
    missed_count: int
    missed_tasks: list[dict]
    total_pts_missed: int


class GetMissedTasksTool(BaseTool):
    name = "get_missed_tasks"
    description = (
        "Returns tasks that have already passed their end time "
        "but were not completed. Use this to understand what the user missed "
        "and decide whether to intervene."
    )
    input_schema = GetMissedTasksInput
    output_schema = GetMissedTasksOutput

    async def execute(
        self, input: GetMissedTasksInput, context: ToolContext
    ) -> GetMissedTasksOutput:
        try:
            target = (
                date.fromisoformat(input.target_date)
                if input.target_date
                else clock.today()
            )
            tasks = await task_repo.get_tasks_for_date(target)
        except Exception as e:
            raise ToolExecutionError(f"Failed to load tasks: {e}") from e

        now = clock.now().time()
        missed = [
            t for t in tasks
            if t.is_past_at(now) and not t.completed
            and t.task_class.value not in ("Deviated", "Sleep", "Break")
        ]

        return GetMissedTasksOutput(
            missed_count=len(missed),
            missed_tasks=[GetCurrentTasksTool._task_to_dict(t) for t in missed],
            total_pts_missed=sum(t.points for t in missed),
        )
