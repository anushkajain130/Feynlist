"""
The example day template shipped in the frontend (frontend/src/lib/dayTemplate.json):
it saves through the API and its midnight-crossing Sleep block behaves correctly.
"""

import json
from datetime import date, time
from pathlib import Path

from analytics.metrics import DisciplineMetric
from core.models import Task, TaskClass

TEMPLATE = json.loads(
    (Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "dayTemplate.json").read_text()
)
ALLOWED_CLASSES = {"Academics_Selfstudy", "Academic_Classes", "Project", "Book_Reading",
                   "Yoga_and_Wellness", "Break", "Sleep"}


def as_tasks():
    return [Task(date=date(2026, 1, 5), task=t["name"], start_time=t["start_time"],
                 end_time=t["end_time"], task_class=TaskClass(t["task_class"]), points=50)
            for t in TEMPLATE]


def test_template_uses_only_picker_classes():
    assert {t["task_class"] for t in TEMPLATE} <= ALLOWED_CLASSES


def test_template_has_exactly_one_midnight_crossing_sleep_block():
    crossing = [t for t in as_tasks() if t.ends_next_day]
    assert [t.task_class for t in crossing] == [TaskClass.SLEEP]


def test_sleep_block_not_counted_missed_during_the_day():
    tasks = as_tasks()
    for t in tasks:
        if t.end_time_obj <= time(18, 0) and not t.ends_next_day:
            t.start_and_sit = True
    # Every block that has ended by 18:00 was started -> 100%, the Sleep block is not "missed".
    assert DisciplineMetric.compute_raw(tasks, now=time(18, 0)) == 100.0
    sleep = next(t for t in tasks if t.ends_next_day)
    assert not sleep.is_past_at(time(23, 59))
    assert sleep.is_active_at(time(23, 30))


async def test_template_saves_via_api(client):
    r = await client.post("/api/tasks/schedule", json={"tasks": TEMPLATE})
    assert r.status_code == 201
    assert r.json()["tasks_created"] == len(TEMPLATE)
    r = await client.get("/api/tasks/today")
    names = [t["task"] for t in r.json()["tasks"]]
    assert "Sleep" in names
