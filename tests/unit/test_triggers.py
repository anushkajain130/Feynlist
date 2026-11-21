"""
Persona triggers must be real: every routed event has an emitter in the code and
a rule that dispatches it, and persona YAML lists exactly the events routed to it.
"""

import re
from pathlib import Path

import pytest
import yaml

from agents.orchestrator import EVENT_AGENT_MAP
from core.models import EventType
from events.rules_engine import RulesEngine

ROOT = Path(__file__).resolve().parents[2]
NAMES = ["freya", "anya", "zerotwo", "albedo", "mohini"]
REMOVED = ["inactivity_detected", "low_energy_detected", "high_score",
           "performance_drop", "week_review"]


def emitters_in_source() -> set[str]:
    """Event names constructed in app code (excluding routing/rules definitions)."""
    found = set()
    for path in ROOT.glob("**/*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith((".venv", "tests/", "frontend/")) or rel in (
            "agents/orchestrator.py", "events/rules_engine.py", "core/models.py"):
            continue
        for m in re.finditer(r"event_type=EventType\.([A-Z_]+)", path.read_text(encoding="utf-8")):
            found.add(EventType[m.group(1)].value)
    return found


def rule_events() -> set[str]:
    import events.rules_engine as re_mod
    engine = RulesEngine()
    original = re_mod.rules_engine
    re_mod.rules_engine = engine
    try:
        re_mod.register_default_rules(orchestrator=object())
    finally:
        re_mod.rules_engine = original
    return {r["event"] for r in engine.list_rules()}


def test_every_routed_event_is_emitted_and_has_a_rule():
    emitted, rules = emitters_in_source(), rule_events()
    for event in EVENT_AGENT_MAP:
        assert event.value in emitted, f"{event.value} is routed but nothing emits it"
        assert event.value in rules, f"{event.value} is emitted but no rule dispatches it"


@pytest.mark.parametrize("name", NAMES)
def test_persona_triggers_match_routing(name):
    cfg = yaml.safe_load((ROOT / "agents" / "personas" / f"{name}.yaml").read_text())
    routed = {e.value for e, a in EVENT_AGENT_MAP.items() if a.value == name}
    assert set(cfg["triggers"]) == routed | {"user_direct_message"}


@pytest.mark.parametrize("event", REMOVED)
def test_unemitted_triggers_not_claimed(event):
    assert event not in {e.value for e in EVENT_AGENT_MAP}
    for name in NAMES:
        cfg = yaml.safe_load((ROOT / "agents" / "personas" / f"{name}.yaml").read_text())
        assert event not in cfg["triggers"]
