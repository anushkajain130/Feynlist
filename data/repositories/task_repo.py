"""
Task Repository
===============
All database operations for tasks.
Zero pandas. Zero CSV. Pure async SQLite.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Optional

from loguru import logger

from core.models import Task, TaskClass
from core.exceptions import RecordNotFoundError, DatabaseError
from data.database import db, row_to_dict, dump_json_field


class TaskRepository:
    """CRUD operations for the tasks table."""

    # ------------------------------------------------------------------
    # READ
    # ------------------------------------------------------------------

    async def get_by_id(self, task_id: str) -> Task:
        """Fetch a single task by its ID."""
        row = await db.fetch_one(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        )
        if not row:
            raise RecordNotFoundError("Task", task_id)
        return self._row_to_task(row)

    async def get_tasks_for_date(self, target_date: date) -> list[Task]:
        """Fetch all tasks for a specific date, ordered by start_time."""
        rows = await db.fetch_all(
            "SELECT * FROM tasks WHERE date = ? ORDER BY start_time ASC",
            (target_date.isoformat(),),
        )
        return [self._row_to_task(r) for r in rows]

    async def get_tasks_in_range(
        self, start: date, end: date
    ) -> list[Task]:
        """Fetch all tasks between start and end dates (inclusive)."""
        rows = await db.fetch_all(
            """
            SELECT * FROM tasks
            WHERE date BETWEEN ? AND ?
            ORDER BY date ASC, start_time ASC
            """,
            (start.isoformat(), end.isoformat()),
        )
        return [self._row_to_task(r) for r in rows]

    async def get_current_task(self, target_date: date) -> Optional[Task]:
        """
        Returns the task whose time window contains right now.
        Returns None if no task is currently scheduled.
        """
        now_str = datetime.now().strftime("%H:%M")
        row = await db.fetch_one(
            """
            SELECT * FROM tasks
            WHERE date = ? AND start_time <= ? AND end_time >= ?
            ORDER BY start_time ASC
            LIMIT 1
            """,
            (target_date.isoformat(), now_str, now_str),
        )
        return self._row_to_task(row) if row else None

    async def get_completed_count_for_date(self, target_date: date) -> int:
        """Count completed tasks for a date."""
        row = await db.fetch_one(
            "SELECT COUNT(*) as c FROM tasks WHERE date = ? AND completed = 1",
            (target_date.isoformat(),),
        )
        return row["c"] if row else 0

    async def get_dates_with_data(self) -> list[date]:
        """Return all distinct dates that have tasks."""
        rows = await db.fetch_all(
            "SELECT DISTINCT date FROM tasks ORDER BY date ASC"
        )
        return [date.fromisoformat(r["date"]) for r in rows]

    # ------------------------------------------------------------------
    # WRITE
    # ------------------------------------------------------------------

    async def upsert(self, task: Task) -> None:
        """
        Insert a task or update it if it already exists (by ID).
        Used for both initial creation and status updates.
        """
        async with db.connection() as conn:
            await conn.execute(
                """
                INSERT INTO tasks (
                    id, date, task, start_time, end_time, points, completed,
                    task_class, sub_class, sub_class2, start_and_sit,
                    complete_task, be_attentive, slider_val, ps_var,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(id) DO UPDATE SET
                    completed     = excluded.completed,
                    task_class    = excluded.task_class,
                    sub_class     = excluded.sub_class,
                    sub_class2    = excluded.sub_class2,
                    start_and_sit = excluded.start_and_sit,
                    complete_task = excluded.complete_task,
                    be_attentive  = excluded.be_attentive,
                    slider_val    = excluded.slider_val,
                    ps_var        = excluded.ps_var,
                    updated_at    = datetime('now')
                """,
                (
                    task.id,
                    task.date.isoformat(),
                    task.task,
                    task.start_time,
                    task.end_time,
                    task.points,
                    int(task.completed),
                    task.task_class.value,
                    task.sub_class,
                    task.sub_class2,
                    int(task.start_and_sit),
                    int(task.complete_task),
                    int(task.be_attentive),
                    task.slider_val,
                    task.ps_var,
                ),
            )
            await conn.commit()
        logger.debug(f"Upserted task: {task.id} ({task.task[:30]})")

    async def bulk_upsert(self, tasks: list[Task]) -> None:
        """Efficiently upsert multiple tasks in a single transaction."""
        async with db.connection() as conn:
            await conn.executemany(
                """
                INSERT INTO tasks (
                    id, date, task, start_time, end_time, points, completed,
                    task_class, sub_class, sub_class2, start_and_sit,
                    complete_task, be_attentive, slider_val, ps_var,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(id) DO UPDATE SET
                    completed     = excluded.completed,
                    task_class    = excluded.task_class,
                    sub_class     = excluded.sub_class,
                    sub_class2    = excluded.sub_class2,
                    start_and_sit = excluded.start_and_sit,
                    complete_task = excluded.complete_task,
                    be_attentive  = excluded.be_attentive,
                    slider_val    = excluded.slider_val,
                    ps_var        = excluded.ps_var,
                    updated_at    = datetime('now')
                """,
                [
                    (
                        t.id, t.date.isoformat(), t.task, t.start_time, t.end_time,
                        t.points, int(t.completed), t.task_class.value,
                        t.sub_class, t.sub_class2, int(t.start_and_sit),
                        int(t.complete_task), int(t.be_attentive),
                        t.slider_val, t.ps_var,
                    )
                    for t in tasks
                ],
            )
            await conn.commit()
        logger.info(f"Bulk upserted {len(tasks)} tasks.")

    async def toggle_subtask(
        self,
        task_id: str,
        subtask_name: str,
        value: bool,
        slider_val: Optional[int] = None,
    ) -> Task:
        """
        Toggle a specific subtask on a task.
        Returns the updated task.
        """
        field_map = {
            "Start_and_Sit_for_5_mins": "start_and_sit",
            "Complete_the_task": "complete_task",
            "Be_attentive": "be_attentive",
        }
        if subtask_name not in field_map:
            raise DatabaseError(f"Unknown subtask name: '{subtask_name}'")

        col = field_map[subtask_name]
        async with db.connection() as conn:
            if subtask_name == "Be_attentive":
                if slider_val is None:
                    slider_val = 100 if value else 0
                await conn.execute(
                    f"UPDATE tasks SET {col} = ?, slider_val = ?, updated_at = datetime('now') WHERE id = ?",
                    (int(value), slider_val, task_id),
                )
            else:
                await conn.execute(
                    f"UPDATE tasks SET {col} = ?, updated_at = datetime('now') WHERE id = ?",
                    (int(value), task_id),
                )

            # Mark task completed if all 3 subtasks done
            await conn.execute(
                """
                UPDATE tasks SET completed = (
                    start_and_sit = 1 AND complete_task = 1 AND be_attentive = 1
                ), updated_at = datetime('now')
                WHERE id = ?
                """,
                (task_id,),
            )
            await conn.commit()

        return await self.get_by_id(task_id)

    async def toggle_complete(
        self,
        task_id: str,
        completed: bool,
        slider_val: int = 100,
    ) -> Task:
        """
        Toggle the overall task completion.
        If marking complete: completed=1, start_and_sit=1, complete_task=1, be_attentive=1, slider_val=100.
        If marking incomplete: completed=0, start_and_sit=0, complete_task=0, be_attentive=0, slider_val=100.
        """
        async with db.connection() as conn:
            val = 1 if completed else 0
            s_val = slider_val if completed else 100
            await conn.execute(
                """
                UPDATE tasks
                SET completed = ?, start_and_sit = ?, complete_task = ?, be_attentive = ?, slider_val = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (val, val, val, val, s_val, task_id),
            )
            await conn.commit()
        return await self.get_by_id(task_id)

    async def delete_for_date(self, target_date: date) -> int:
        """Delete all tasks for a given date. Returns rows deleted."""
        async with db.connection() as conn:
            async with conn.execute(
                "DELETE FROM tasks WHERE date = ?", (target_date.isoformat(),)
            ) as cursor:
                await conn.commit()
                return cursor.rowcount

    # ------------------------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_task(row) -> Task:
        """Convert a database row to a Task model."""
        d = dict(row)
        return Task(
            id=d["id"],
            date=date.fromisoformat(d["date"]),
            task=d["task"],
            start_time=d["start_time"],
            end_time=d["end_time"],
            points=d["points"],
            completed=bool(d["completed"]),
            task_class=TaskClass(d["task_class"]),
            sub_class=d.get("sub_class"),
            sub_class2=d.get("sub_class2"),
            start_and_sit=bool(d.get("start_and_sit", 0)),
            complete_task=bool(d.get("complete_task", 0)),
            be_attentive=bool(d.get("be_attentive", 0)),
            slider_val=d.get("slider_val", 0),
            ps_var=d.get("ps_var", 0.0),
        )


# Singleton
task_repo = TaskRepository()
