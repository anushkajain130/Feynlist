"""
Tasks Router
============
All task-related API endpoints.

GET  /api/tasks/today            — today's full task list
GET  /api/tasks/{date}           — task list for a specific date
POST /api/tasks/toggle-subtask   — mark a subtask done/undone
GET  /api/tasks/current          — the task active right now
"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from api.schemas import (
    TaskListResponse, TaskResponse,
    ToggleSubtaskRequest, ToggleSubtaskResponse,
    ToggleCompleteRequest, ToggleCompleteResponse,
    ScheduleRequest,
)
from core.models import Task
from data.repositories.task_repo import task_repo
from core.exceptions import RecordNotFoundError, DatabaseError
from notifications.triggers import emit_task_completed, fire_and_forget
from analytics.pipeline import pipeline

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


def _task_to_response(task: Task) -> TaskResponse:
    return TaskResponse(
        id=task.id,
        date=task.date.isoformat(),
        task=task.task,
        start_time=task.start_time,
        end_time=task.end_time,
        points=task.points,
        completed=task.completed,
        task_class=task.task_class.value,
        sub_class=task.sub_class,
        sub_class2=task.sub_class2,
        start_and_sit=task.start_and_sit,
        complete_task=task.complete_task,
        be_attentive=task.be_attentive,
        slider_val=task.slider_val,
        ps_var=task.ps_var,
    )


@router.get("/today", response_model=TaskListResponse)
async def get_today_tasks():
    """Return today's full task list with completion stats."""
    today = date.today()
    try:
        tasks = await task_repo.get_tasks_for_date(today)
    except DatabaseError as e:
        logger.error(f"Task DB error: {e}")
        raise HTTPException(status_code=500, detail="Could not load or save tasks. Please try again.")

    completed = sum(1 for t in tasks if t.completed)
    pct = round(completed / len(tasks) * 100, 1) if tasks else 0.0

    return TaskListResponse(
        date=today.isoformat(),
        tasks=[_task_to_response(t) for t in tasks],
        total=len(tasks),
        completed=completed,
        completion_pct=pct,
    )


@router.get("/{target_date}", response_model=TaskListResponse)
async def get_tasks_for_date(target_date: str):
    """Return tasks for a specific date (YYYY-MM-DD)."""
    try:
        d = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid date: {target_date}")

    try:
        tasks = await task_repo.get_tasks_for_date(d)
    except DatabaseError as e:
        logger.error(f"Task DB error: {e}")
        raise HTTPException(status_code=500, detail="Could not load or save tasks. Please try again.")

    completed = sum(1 for t in tasks if t.completed)
    pct = round(completed / len(tasks) * 100, 1) if tasks else 0.0

    return TaskListResponse(
        date=d.isoformat(),
        tasks=[_task_to_response(t) for t in tasks],
        total=len(tasks),
        completed=completed,
        completion_pct=pct,
    )


@router.get("/today/current", response_model=TaskResponse | None)
async def get_current_task():
    """Return the task currently active (by time window). Null if none."""
    now = datetime.now().time()
    tasks = await task_repo.get_tasks_for_date(date.today())
    current = next((t for t in tasks if t.is_active_at(now)), None)
    return _task_to_response(current) if current else None


@router.post("/toggle-subtask", response_model=ToggleSubtaskResponse)
async def toggle_subtask(req: ToggleSubtaskRequest):
    """
    Mark a subtask as done or undone.
    Automatically recalculates today's analytics after the update.
    """
    try:
        before = await task_repo.get_by_id(req.task_id)
        updated_task = await task_repo.toggle_subtask(
            task_id=req.task_id,
            subtask_name=req.subtask_name,
            value=req.value,
            slider_val=req.slider_val,
        )
    except RecordNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DatabaseError as e:
        logger.error(f"Task DB error: {e}")
        raise HTTPException(status_code=500, detail="Could not load or save tasks. Please try again.")

    # Recalculate analytics (non-blocking — fire and move on)
    try:
        await pipeline.run(updated_task.date)
    except Exception as e:
        logger.warning(f"Analytics recalc failed after subtask toggle: {e}")

    if updated_task.completed and not before.completed:
        fire_and_forget(emit_task_completed(updated_task))

    return ToggleSubtaskResponse(
        success=True,
        task=_task_to_response(updated_task),
    )


@router.post("/toggle-complete", response_model=ToggleCompleteResponse)
async def toggle_complete(req: ToggleCompleteRequest):
    """
    Toggle overall task completion (shortcut or expanded complete).
    Automatically sets slider_val and all subtasks.
    """
    try:
        before = await task_repo.get_by_id(req.task_id)
        updated_task = await task_repo.toggle_complete(
            task_id=req.task_id,
            completed=req.completed,
            slider_val=req.slider_val,
        )
    except RecordNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DatabaseError as e:
        logger.error(f"Task DB error: {e}")
        raise HTTPException(status_code=500, detail="Could not load or save tasks. Please try again.")

    # Recalculate analytics in background
    try:
        await pipeline.run(updated_task.date)
    except Exception as e:
        logger.warning(f"Analytics recalc failed after task toggle-complete: {e}")

    if updated_task.completed and not before.completed:
        fire_and_forget(emit_task_completed(updated_task))

    return ToggleCompleteResponse(
        success=True,
        task=_task_to_response(updated_task),
    )


@router.post("/schedule", status_code=201)
async def set_schedule(req: ScheduleRequest):
    """
    Bulk-create or replace today's (or any day's) task schedule.
    Clears existing tasks for that date first, then inserts the new list.
    """
    from api.schemas import ScheduleItemIn
    from core.models import Task, TaskClass
    import uuid

    try:
        target = date.fromisoformat(req.date) if req.date else date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    # Clear existing tasks for this date
    deleted = await task_repo.delete_for_date(target)
    logger.info(f"Cleared {deleted} existing tasks for {target}")

    # Build Task objects
    tasks: list[Task] = []
    for item in req.tasks:
        try:
            tc = TaskClass(item.task_class)
        except ValueError:
            tc = TaskClass.UNSPECIFIED

        # Derive points from class
        POINTS_MAP = {
            "Academics_Selfstudy": 100, "Academic_Classes": 80, "Project": 90,
            "Work": 85, "Side_Business": 80, "Book_Reading": 70,
            "Yoga_and_Wellness": 60, "Self_Growth": 65, "ExtraActi": 50,
            "Social": 40, "Break": 20, "Sleep": 10, "Unspecified": 30,
        }
        points = POINTS_MAP.get(tc.value, 30)

        task_obj = Task(
            id=str(uuid.uuid4()),
            date=target,
            task=item.name,
            start_time=item.start_time,
            end_time=item.end_time,
            points=points,
            completed=False,
            task_class=tc,
            sub_class=item.sub_class,
        )
        tasks.append(task_obj)

    await task_repo.bulk_upsert(tasks)
    logger.info(f"Scheduled {len(tasks)} tasks for {target}")

    return {"date": target.isoformat(), "tasks_created": len(tasks)}


@router.delete("/{target_date}", status_code=200)
async def delete_day_schedule(target_date: str):
    """Delete all tasks for a given date."""
    try:
        d = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format.")
    deleted = await task_repo.delete_for_date(d)
    return {"date": target_date, "tasks_deleted": deleted}

