"""
Free-tier AI budget: 2 live replies per session (chat + demo controls together),
a global daily cap, a per-minute guard, failures don't use up a session's reply,
the all-five Council and automatic nudges are samples in the demo, and every
sample is labelled. The model is stubbed: no real LLM calls.
"""

import uuid

import httpx
import pytest
import yaml

from agents.ai_budget import SAMPLE_REASONS
from agents.runtime import AgentRuntime, PERSONAS_DIR
from config.settings import settings

LABEL = "Sample reply (pre-written, not live)"


class Boom(Exception):
    code = 429


@pytest.fixture
def stub(monkeypatch):
    """A fake key + fake model. `stub.fail = True` makes the next calls 429."""
    class S:
        fail = False
        calls = 0
    state = S()

    async def fake_init(self):
        self._config = yaml.safe_load((PERSONAS_DIR / f"{self.agent_id.value}.yaml").read_text())
        self._client = object()
        self._initialized = True

    async def fake_call(self, context):
        state.calls += 1
        if state.fail:
            raise Boom("RESOURCE_EXHAUSTED secret provider detail")
        return f"[{self.agent_id.value}] live reply.", 10, 5, 15, "stub-model", False

    monkeypatch.setattr(settings, "gemini_api_key", "test-key-not-real")
    monkeypatch.setattr(AgentRuntime, "initialize", fake_init)
    monkeypatch.setattr(AgentRuntime, "_call_llm", fake_call)
    return state


@pytest.fixture
async def demo(tmp_path, monkeypatch, stub):
    from agents import orchestrator as orch_mod
    from data import database as db_mod
    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(settings, "demo_data_dir", tmp_path / "sessions")
    monkeypatch.setattr(settings, "live_ai_daily_cap", 50)
    monkeypatch.setattr(settings, "live_ai_per_minute", 50)
    monkeypatch.setattr(settings, "enable_proactive_llm", False)
    monkeypatch.setattr(db_mod, "session_databases", db_mod.SessionDatabases())
    monkeypatch.setattr(orch_mod, "_session_orchestrators", orch_mod.OrderedDict())
    from agents.orchestrator import orchestrator
    from core.startup import _wire_event_bus
    from events.rules_engine import register_default_rules
    _wire_event_bus()
    register_default_rules(orchestrator)
    from api.main import app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        yield c


def H(s):
    return {"X-Feynlist-Session": s, "X-Feynlist-TZ": "UTC"}


async def chat(c, s, agent="freya"):
    r = await c.post("/api/agents/message", headers=H(s), json={"message": "hi", "agent_id": agent})
    assert r.status_code == 200, r.text
    return r.json()["messages"][0]


async def test_two_live_replies_then_samples(demo, stub):
    s = uuid.uuid4().hex
    assert (await demo.get("/api/agents/budget", headers=H(s))).json()["live_left"] == 2
    first, second = await chat(demo, s), await chat(demo, s, "anya")
    assert not first["is_sample"] and not second["is_sample"]
    third = await chat(demo, s, "zerotwo")
    assert third["is_sample"] and third["sample_label"] == LABEL
    assert third["sample_reason"] == SAMPLE_REASONS["session_limit"]
    b = (await demo.get("/api/agents/budget", headers=H(s))).json()
    assert b["live_left"] == 0 and b["mode"] == "sample"
    assert stub.calls == 2


async def test_demo_controls_and_chat_share_the_budget(demo):
    s = uuid.uuid4().hex
    r = await demo.post("/api/demo/trigger/check-in", headers=H(s))
    assert not r.json()["messages"][0]["is_sample"]
    assert not (await chat(demo, s))["is_sample"]
    assert (await chat(demo, s))["is_sample"]


async def test_reset_demo_does_not_refill(demo):
    s = uuid.uuid4().hex
    await chat(demo, s); await chat(demo, s)
    await demo.post("/api/demo/reset", headers=H(s))
    assert (await chat(demo, s))["sample_reason"] == SAMPLE_REASONS["session_limit"]


async def test_sessions_have_separate_budgets(demo):
    a, b = uuid.uuid4().hex, uuid.uuid4().hex
    await chat(demo, a); await chat(demo, a)
    assert not (await chat(demo, b))["is_sample"]


async def test_global_daily_cap(demo, monkeypatch):
    monkeypatch.setattr(settings, "live_ai_daily_cap", 1)
    a, b = uuid.uuid4().hex, uuid.uuid4().hex
    assert not (await chat(demo, a))["is_sample"]
    m = await chat(demo, b)
    assert m["is_sample"] and m["sample_reason"] == SAMPLE_REASONS["daily_cap"]
    assert (await demo.get("/api/agents/budget", headers=H(b))).json()["daily_cap_reached"] is True


async def test_per_minute_guard(demo, monkeypatch):
    monkeypatch.setattr(settings, "live_ai_per_minute", 1)
    a, b = uuid.uuid4().hex, uuid.uuid4().hex
    assert not (await chat(demo, a))["is_sample"]
    assert (await chat(demo, b))["sample_reason"] == SAMPLE_REASONS["rate_limit"]


async def test_failed_call_does_not_use_up_a_live_reply(demo, stub):
    s = uuid.uuid4().hex
    stub.fail = True
    m = await chat(demo, s)
    assert m["is_sample"] and m["sample_reason"] == SAMPLE_REASONS["quota"]
    assert "RESOURCE_EXHAUSTED" not in str(m)
    stub.fail = False
    assert (await demo.get("/api/agents/budget", headers=H(s))).json()["live_left"] == 2


async def test_council_is_sample_in_demo(demo, stub):
    s = uuid.uuid4().hex
    r = await demo.post("/api/agents/message", headers=H(s), json={"message": "hi council"})
    msgs = r.json()["messages"]
    assert len(msgs) == 5
    assert all(m["is_sample"] and m["sample_reason"] == SAMPLE_REASONS["council_demo"] for m in msgs)
    assert stub.calls == 0
    assert (await demo.get("/api/agents/budget", headers=H(s))).json()["live_left"] == 2


async def test_automatic_nudge_is_sample_and_free(demo, stub):
    """Ticking a task off fires Albedo automatically: sample, no budget used."""
    import asyncio
    s = uuid.uuid4().hex
    tasks = (await demo.get("/api/tasks/today", headers=H(s))).json()["tasks"]
    open_task = next(t for t in tasks if not t["completed"])
    await demo.post("/api/tasks/toggle-complete", headers=H(s), json={"task_id": open_task["id"], "completed": True})
    await asyncio.sleep(0.2)
    nudges = (await demo.get("/api/agents/nudges", headers=H(s))).json()["nudges"]
    assert nudges and nudges[0]["agent_id"] == "albedo"
    assert nudges[0]["is_sample"] and nudges[0]["sample_label"] == LABEL
    assert nudges[0]["sample_reason"] == SAMPLE_REASONS["proactive_off"]
    assert stub.calls == 0


def test_no_scheduled_llm_jobs_by_default(monkeypatch):
    from notifications.scheduler import FeynlistScheduler
    monkeypatch.setattr(settings, "enable_proactive_llm", False)
    sched = FeynlistScheduler(); sched.setup_jobs()
    assert [j["id"] for j in sched.list_jobs()] == ["analytics_pipeline"]
    monkeypatch.setattr(settings, "enable_proactive_llm", True)
    monkeypatch.setattr(settings, "demo_mode", False)
    sched = FeynlistScheduler(); sched.setup_jobs()
    assert len(sched.list_jobs()) == 5
