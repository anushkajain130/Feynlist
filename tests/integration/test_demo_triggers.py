"""
Demo controls fire the real event paths: the right coach answers, the reply is
returned, stored as a nudge and pushed to that session's websocket only.
The model is stubbed (no real LLM calls).
"""

import uuid

import httpx
import pytest
import yaml

from agents.runtime import AgentRuntime, PERSONAS_DIR
from config.settings import settings


def _setup(tmp_path, monkeypatch):
    from agents import orchestrator as orch_mod
    from data import database as db_mod
    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(settings, "demo_data_dir", tmp_path)
    monkeypatch.setattr(db_mod, "session_databases", db_mod.SessionDatabases())
    monkeypatch.setattr(orch_mod, "_session_orchestrators", orch_mod.OrderedDict())

    async def fake_init(self):
        self._config = yaml.safe_load((PERSONAS_DIR / f"{self.agent_id.value}.yaml").read_text())
        self._client = object()
        self._initialized = True

    async def fake_call(self, context):
        return f"[{self.agent_id.value}] stub reply.", 10, 5, 15, "stub-model", False

    monkeypatch.setattr(AgentRuntime, "initialize", fake_init)
    monkeypatch.setattr(AgentRuntime, "_call_llm", fake_call)
    # The app lifespan doesn't run in these tests: wire events like startup() does.
    from agents.orchestrator import orchestrator
    from core.startup import _wire_event_bus
    from events.rules_engine import register_default_rules
    _wire_event_bus()
    register_default_rules(orchestrator)


@pytest.fixture
async def demo_client(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    from api.main import app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


def H(s):
    return {"X-Feynlist-Session": s, "X-Feynlist-TZ": "UTC"}


@pytest.mark.parametrize("kind,agent", [
    ("missed-task", "freya"),
    ("complete-task", "albedo"),
    ("end-of-day", "anya"),
    ("check-in", "zerotwo"),
])
async def test_trigger_routes_to_right_coach(demo_client, kind, agent):
    s = uuid.uuid4().hex
    r = await demo_client.post(f"/api/demo/trigger/{kind}", headers=H(s))
    assert r.status_code == 200
    body = r.json()
    assert body["cooldowns_bypassed"] is True
    assert body["messages"], body
    assert agent in [m["agent_id"] for m in body["messages"]], body["messages"]
    nudges = (await demo_client.get("/api/agents/nudges", headers=H(s))).json()["nudges"]
    assert agent in [n["agent_id"] for n in nudges]


async def test_repeated_triggers_bypass_cooldowns(demo_client):
    s = uuid.uuid4().hex
    for _ in range(2):
        r = await demo_client.post("/api/demo/trigger/check-in", headers=H(s))
        assert r.json()["messages"], "second demo trigger should not be blocked by cooldowns"


async def test_complete_task_actually_completes_one(demo_client):
    s = uuid.uuid4().hex
    before = (await demo_client.get("/api/tasks/today", headers=H(s))).json()["completed"]
    await demo_client.post("/api/demo/trigger/complete-task", headers=H(s))
    after = (await demo_client.get("/api/tasks/today", headers=H(s))).json()["completed"]
    assert after == before + 1


async def test_nudges_are_per_session(demo_client):
    a, b = uuid.uuid4().hex, uuid.uuid4().hex
    await demo_client.post("/api/demo/trigger/check-in", headers=H(a))
    assert (await demo_client.get("/api/agents/nudges", headers=H(b))).json()["nudges"] == []


def test_proactive_push_reaches_only_that_sessions_socket(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    from fastapi.testclient import TestClient
    from api.main import app
    a, b = uuid.uuid4().hex, uuid.uuid4().hex
    client = TestClient(app)
    with client.websocket_connect(f"/api/agents/ws?session={a}&tz=UTC") as ws_a, \
         client.websocket_connect(f"/api/agents/ws?session={b}&tz=UTC") as ws_b:
        ws_a.receive_json(); ws_b.receive_json()            # "connected" status
        r = client.post("/api/demo/trigger/check-in", headers=H(a))
        assert r.status_code == 200
        pushed = ws_a.receive_json()
        assert pushed["proactive"] is True and pushed["agent_id"] == "zerotwo"
        ws_b.send_json({"message": ""})                     # b gets only its own reply
        assert ws_b.receive_json()["type"] == "error"


async def test_chat_not_blocked_by_global_cooldown(demo_client):
    s = uuid.uuid4().hex
    await demo_client.post("/api/demo/trigger/check-in", headers=H(s))   # sets global cooldown
    r = await demo_client.post("/api/agents/message", headers=H(s), json={"message": "hi"})
    assert r.status_code == 200 and r.json()["messages"]
