"""Completing a task emits TASK_COMPLETED once (Albedo's trigger); un-completing doesn't."""

import asyncio

from core.models import EventType


async def test_task_completed_emitted_once(client, monkeypatch):
    import notifications.triggers as trig
    seen = []

    async def record(event):
        seen.append(event)

    monkeypatch.setattr(trig.event_bus, "publish", record)

    await client.post("/api/tasks/schedule", json={"tasks": [
        {"name": "Study block", "start_time": "08:00", "end_time": "09:00", "task_class": "Academics_Selfstudy"}]})
    tid = (await client.get("/api/tasks/today")).json()["tasks"][0]["id"]

    r = await client.post("/api/tasks/toggle-complete", json={"task_id": tid, "completed": True, "slider_val": 80})
    assert r.status_code == 200
    await asyncio.sleep(0.05)  # emitted in the background
    assert [e.event_type for e in seen] == [EventType.TASK_COMPLETED]
    assert seen[0].payload["task_name"] == "Study block"

    await client.post("/api/tasks/toggle-complete", json={"task_id": tid, "completed": True, "slider_val": 80})
    await client.post("/api/tasks/toggle-complete", json={"task_id": tid, "completed": False})
    await asyncio.sleep(0.05)
    assert len(seen) == 1


async def test_completing_via_last_subtask_emits(client, monkeypatch):
    import notifications.triggers as trig
    seen = []

    async def record(event):
        seen.append(event)

    monkeypatch.setattr(trig.event_bus, "publish", record)
    await client.post("/api/tasks/schedule", json={"tasks": [
        {"name": "Reading", "start_time": "10:00", "end_time": "11:00", "task_class": "Book_Reading"}]})
    tid = (await client.get("/api/tasks/today")).json()["tasks"][0]["id"]
    for name in ("Start_and_Sit_for_5_mins", "Complete_the_task"):
        await client.post("/api/tasks/toggle-subtask", json={"task_id": tid, "subtask_name": name, "value": True})
    await asyncio.sleep(0.05)
    assert seen == []
    await client.post("/api/tasks/toggle-subtask", json={"task_id": tid, "subtask_name": "Be_attentive", "value": True, "slider_val": 70})
    await asyncio.sleep(0.05)
    assert [e.event_type for e in seen] == [EventType.TASK_COMPLETED]
