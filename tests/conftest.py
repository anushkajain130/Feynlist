"""Shared test setup: never touch the real AI budget file."""

import pytest


@pytest.fixture(autouse=True)
def _isolated_ai_budget(tmp_path, monkeypatch):
    from config.settings import settings
    monkeypatch.setattr(settings, "ai_budget_path", tmp_path / "ai_budget.db")
    from agents.ai_budget import ai_budget
    ai_budget._minute.clear()
