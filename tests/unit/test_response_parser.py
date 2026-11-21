"""
Unit Tests: response parsing and truncation handling (issue 4). No real LLM calls.
"""

from types import SimpleNamespace

import pytest
from google.genai import types as genai_types

from agents.response_parser import ResponseParser, MAX_RESPONSE_CHARS
from agents.runtime import AgentRuntime
from core.models import AgentId

parser = ResponseParser()


def test_complete_reply_untouched():
    text = "Your 10:00 block slipped. Move it to 14:00?"
    assert parser.parse(text, "freya").content == text


def test_token_limited_reply_trimmed_to_last_sentence():
    raw = "Discipline is 82% today, nice. Next up is Reading at 16:00 so start it on ti"
    out = parser.parse(raw, "freya", truncated=True).content
    assert out == "Discipline is 82% today, nice."


def test_token_limited_reply_without_sentence_end_gets_ellipsis():
    raw = "Discipline is 82% today and the next block is Reading at sixteen hundred so"
    out = parser.parse(raw, "freya", truncated=True).content
    assert out == "Discipline is 82% today and the next block is Reading at sixteen hundred…"


def test_overlong_reply_cut_at_sentence_boundary():
    raw = ("This is a sentence. " * 100).strip()
    out = parser.parse(raw, "zerotwo").content
    assert len(out) <= MAX_RESPONSE_CHARS
    assert out.endswith(".")


class FakeModels:
    def __init__(self, finish_reason):
        self.finish_reason = finish_reason
        self.last_config = None

    async def generate_content(self, model, contents, config):
        self.last_config = config
        return SimpleNamespace(
            text="Half a sentence that never",
            candidates=[SimpleNamespace(finish_reason=self.finish_reason)],
            usage_metadata=None,
        )


def make_runtime(model_tier="standard", finish_reason=genai_types.FinishReason.STOP):
    rt = AgentRuntime(AgentId.FREYA)
    rt._config = {"model_tier": model_tier, "system_prompt": "x", "max_output_tokens": 300}
    models = FakeModels(finish_reason)
    rt._client = SimpleNamespace(aio=SimpleNamespace(models=models))
    return rt, models


async def test_flash_thinking_disabled_and_limit_low():
    rt, models = make_runtime()
    await rt._call_llm("ctx")
    cfg = models.last_config
    assert cfg.max_output_tokens == 300
    assert cfg.thinking_config is not None and cfg.thinking_config.thinking_budget == 0


async def test_max_tokens_finish_reason_reported():
    rt, _ = make_runtime(finish_reason=genai_types.FinishReason.MAX_TOKENS)
    *_, truncated = await rt._call_llm("ctx")
    assert truncated is True


async def test_stop_finish_reason_not_truncated():
    rt, _ = make_runtime()
    *_, truncated = await rt._call_llm("ctx")
    assert truncated is False
