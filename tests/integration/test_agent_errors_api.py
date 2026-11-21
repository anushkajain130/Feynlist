"""
API tests: AI failures are shown as short friendly messages, never raw provider errors.
No real LLM calls: the Gemini client is never created (no key) or is stubbed.
"""

import pytest

from agents.orchestrator import orchestrator
from agents.runtime import AgentRuntime
from config.settings import settings
from agents.ai_budget import SAMPLE_REASONS
from core.exceptions import classify_llm_error

SECRET = "RESOURCE_EXHAUSTED quota project 1234 generativelanguage.googleapis.com"


class FakeProviderError(Exception):
    def __init__(self, code, text):
        super().__init__(text)
        self.code = code


@pytest.fixture(autouse=True)
def fresh_orchestrator(monkeypatch):
    """No API key, fresh runtimes and no cooldowns for every test."""
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "google_api_key", "")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    orchestrator._runtimes = {aid: AgentRuntime(aid) for aid in orchestrator._runtimes}
    orchestrator._initialized = False
    orchestrator._global_cooldown_until = 0.0
    yield


def stub_llm(monkeypatch, exc):
    """Let runtimes initialise without a key, then fail the LLM call with `exc`."""
    import yaml
    from agents.runtime import PERSONAS_DIR

    async def fake_init(self):
        self._config = yaml.safe_load((PERSONAS_DIR / f"{self.agent_id.value}.yaml").read_text())
        self._client = object()
        self._initialized = True

    async def fake_call(self, context):
        raise exc

    monkeypatch.setattr(AgentRuntime, "initialize", fake_init)
    monkeypatch.setattr(AgentRuntime, "_call_llm", fake_call)


@pytest.mark.parametrize("code,text,reason", [
    (429, "429 RESOURCE_EXHAUSTED", "quota"),
    (None, "You exceeded your current quota", "quota"),
    (403, "API key not valid", "no_api_key"),
    (503, "The model is overloaded", "provider_error"),
    (None, "something odd", "provider_error"),
])
def test_classify_llm_error(code, text, reason):
    assert classify_llm_error(FakeProviderError(code, text)) == reason


async def test_no_key_direct_message_gets_labelled_sample(client):
    r = await client.post("/api/agents/message", json={"message": "hi", "agent_id": "freya"})
    assert r.status_code == 200
    m = r.json()["messages"][0]
    assert m["is_sample"] is True
    assert m["sample_label"] == "Sample reply (pre-written, not live)"
    assert m["sample_reason"] == SAMPLE_REASONS["no_api_key"]
    assert "GEMINI_API_KEY" not in r.text and ".env" not in r.text


async def test_no_key_routed_message_gets_sample(client):
    r = await client.post("/api/agents/message", json={"message": "hi"})
    assert r.status_code == 200
    assert r.json()["messages"][0]["is_sample"] is True


async def test_quota_error_becomes_sample_without_raw_text(client, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "gemini_api_key", "test-key-not-real")
    monkeypatch.setattr(settings, "ai_budget_path", tmp_path / "budget.db")
    stub_llm(monkeypatch, FakeProviderError(429, SECRET))
    r = await client.post("/api/agents/message", json={"message": "hi", "agent_id": "anya"})
    assert r.status_code == 200
    m = r.json()["messages"][0]
    assert m["is_sample"] is True and m["sample_reason"] == SAMPLE_REASONS["quota"]
    assert "RESOURCE_EXHAUSTED" not in r.text and "googleapis" not in r.text


async def test_quota_error_over_websocket_is_sample(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from api.main import app

    monkeypatch.setattr(settings, "gemini_api_key", "test-key-not-real")
    monkeypatch.setattr(settings, "ai_budget_path", tmp_path / "budget.db")
    stub_llm(monkeypatch, FakeProviderError(429, SECRET))
    client = TestClient(app)
    with client.websocket_connect("/api/agents/ws") as ws:
        assert ws.receive_json()["type"] == "status"          # connected
        ws.send_json({"message": "hi", "agent_id": "freya"})
        assert ws.receive_json()["type"] == "status"          # thinking
        msg = ws.receive_json()
    assert msg["type"] == "agent_message" and msg["is_sample"] is True
    assert msg["sample_reason"] == SAMPLE_REASONS["quota"]
    assert "RESOURCE_EXHAUSTED" not in str(msg)


async def test_status_reports_ai_not_configured(client):
    r = await client.get("/api/agents/status")
    assert r.status_code == 200
    assert r.json()["ai_configured"] is False


def test_persona_models_resolve_to_flash_family():
    for aid, rt in orchestrator._runtimes.items():
        import yaml
        from agents.runtime import PERSONAS_DIR
        rt._config = yaml.safe_load((PERSONAS_DIR / f"{aid.value}.yaml").read_text())
        assert "pro" not in rt.model_name, f"{aid.value} would use {rt.model_name}"
        assert "flash" in rt.model_name
