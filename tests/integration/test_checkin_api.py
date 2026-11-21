"""
API tests: neutral consistency check-in and streak behaviour (temp database).
"""

from datetime import date, timedelta


async def _schedule(client, day: date, n: int = 2):
    tasks = [
        {"name": f"Study block {i}", "start_time": f"{8 + i:02d}:00",
         "end_time": f"{9 + i:02d}:00", "task_class": "Academics_Selfstudy"}
        for i in range(n)
    ]
    r = await client.post("/api/tasks/schedule", json={"date": day.isoformat(), "tasks": tasks})
    assert r.status_code == 201


async def test_checkin_kept_starts_streak(client):
    await _schedule(client, date.today())
    r = await client.post("/api/analytics/check-in", json={"kept_commitment": True})
    assert r.status_code == 200
    body = r.json()
    assert body["kept_commitment"] is True
    assert body["retention_streak"] == 1
    assert "relapsed" not in body


async def test_checkin_not_today_resets(client):
    await _schedule(client, date.today())
    await client.post("/api/analytics/check-in", json={"kept_commitment": True})
    r = await client.post("/api/analytics/check-in", json={"kept_commitment": False})
    assert r.status_code == 200
    assert r.json()["kept_commitment"] is False
    assert r.json()["retention_streak"] == 0


async def test_no_checkin_today_does_not_auto_increment(client):
    """Scheduling tasks alone must not grow the streak (baseline bug B-19)."""
    await _schedule(client, date.today())
    r = await client.get("/api/analytics/today")
    assert r.json()["retention_streak"] == 0
    assert r.json()["kept_commitment"] is None


async def test_streak_carries_over_from_counted_yesterday(client):
    yesterday = date.today() - timedelta(days=1)
    await _schedule(client, yesterday)
    r = await client.post("/api/analytics/check-in",
                          json={"kept_commitment": True, "date": yesterday.isoformat()})
    assert r.json()["retention_streak"] == 1

    await _schedule(client, date.today())
    r = await client.post("/api/analytics/check-in", json={"kept_commitment": True})
    assert r.json()["retention_streak"] == 2


async def test_old_relapsed_payload_rejected(client):
    r = await client.post("/api/analytics/check-in", json={"relapsed": True})
    assert r.status_code == 422
