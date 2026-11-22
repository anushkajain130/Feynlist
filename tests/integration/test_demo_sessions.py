"""
Demo mode: each evaluator session has its own seeded database; sessions never
see each other's data; requests without a session are refused; reset works;
the browser time zone decides what "today" is.
"""

import asyncio
import uuid
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest

from config.settings import settings


@pytest.fixture
async def demo_client(tmp_path, monkeypatch):
    from agents import orchestrator as orch_mod
    from data import database as db_mod
    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(settings, "demo_data_dir", tmp_path)
    monkeypatch.setattr(db_mod, "session_databases", db_mod.SessionDatabases())
    monkeypatch.setattr(orch_mod, "_session_orchestrators", orch_mod.OrderedDict())
    from api.main import app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


def sid():
    return uuid.uuid4().hex


def H(session, tz="UTC"):
    return {"X-Feynlist-Session": session, "X-Feynlist-TZ": tz}


async def test_missing_or_bad_session_rejected(demo_client):
    assert (await demo_client.get("/api/tasks/today")).status_code == 400
    assert (await demo_client.get("/api/tasks/today", headers={"X-Feynlist-Session": "../../etc"})).status_code == 400
    assert (await demo_client.get("/health")).status_code == 200


async def test_new_session_is_seeded_with_two_weeks(demo_client):
    s = sid()
    r = await demo_client.get("/api/analytics/history?days=14", headers=H(s))
    assert r.status_code == 200
    assert len(r.json()) >= 14
    today = (await demo_client.get("/api/tasks/today", headers=H(s))).json()
    assert today["total"] == 12
    st = (await demo_client.get("/api/demo/status", headers=H(s))).json()
    assert st["demo_mode"] is True and st["sample_data"] is True


async def test_sessions_are_isolated(demo_client):
    a, b = sid(), sid()
    await demo_client.post("/api/tasks/schedule", headers=H(a), json={"tasks": [
        {"name": "Only in A", "start_time": "09:00", "end_time": "10:00", "task_class": "Academics_Selfstudy"}]})
    names_a = [t["task"] for t in (await demo_client.get("/api/tasks/today", headers=H(a))).json()["tasks"]]
    names_b = [t["task"] for t in (await demo_client.get("/api/tasks/today", headers=H(b))).json()["tasks"]]
    assert names_a == ["Only in A"]
    assert "Only in A" not in names_b and len(names_b) == 12


async def test_reset_restores_sample_data(demo_client):
    s = sid()
    await demo_client.post("/api/tasks/schedule", headers=H(s), json={"tasks": [
        {"name": "Mine", "start_time": "09:00", "end_time": "10:00", "task_class": "Break"}]})
    assert (await demo_client.post("/api/demo/reset", headers=H(s))).status_code == 200
    names = [t["task"] for t in (await demo_client.get("/api/tasks/today", headers=H(s))).json()["tasks"]]
    assert "Mine" not in names and len(names) == 12


async def test_browser_timezone_decides_today(demo_client):
    s = sid()
    for tz in ("Pacific/Kiritimati", "Pacific/Pago_Pago"):   # UTC+14 and UTC-11: always different dates
        r = await demo_client.get("/api/demo/status", headers=H(s, tz))
        assert r.json()["today"] == datetime.now(ZoneInfo(tz)).date().isoformat()


async def test_concurrent_first_requests_seed_once(demo_client):
    s = sid()
    rs = await asyncio.gather(*[demo_client.get("/api/tasks/today", headers=H(s)) for _ in range(5)])
    assert all(r.status_code == 200 for r in rs)
    assert all(r.json()["total"] == 12 for r in rs)


async def test_demo_endpoints_off_without_demo_mode(client):
    assert (await client.post("/api/demo/reset")).status_code == 404


async def test_old_sessions_evicted_and_files_deleted(demo_client, monkeypatch):
    from data import database as db_mod
    monkeypatch.setattr(settings, "demo_max_sessions", 2)
    first, second, third = sid(), sid(), sid()
    for s in (first, second, third):
        await demo_client.get("/api/tasks/today", headers=H(s))
    path = db_mod.session_databases.path_for(first)
    assert not path.exists()
    assert len(db_mod.session_databases) == 2
