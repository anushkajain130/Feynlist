"""
Unit Tests: Persona configs
============================
Static checks on agents/personas/*.yaml — no LLM calls.
These guard the config shape and the content rules in CLAUDE.md; they do NOT
test how the model actually behaves (that needs live persona evals).
"""

import re
from pathlib import Path

import pytest
import yaml

PERSONAS_DIR = Path(__file__).resolve().parents[2] / "agents" / "personas"
NAMES = ["freya", "anya", "zerotwo", "albedo", "mohini"]

# Terms that must never appear in persona prompts (romantic/possessive framing,
# pet names, body/addiction commentary, private biographical details).
BANNED = [
    r"\bwife\b", r"\bhusband\b", r"\bsoulmate\b", r"\bhoney\b", r"\bdarling\b",
    r"\bsweetheart\b", r"\bbaby\b", r"\blittle one\b", r"good boy", r"mommy",
    r"possessive", r"\bflirt", r"\baddiction\b",
    r"\bjee\b", r"\bgate\b", r"rhotacism", r"upperbite", r"nail polish", r"\bshower\b",
    r"reptilian", r"\bdosha", r"\bprana\b",
]


def load(name):
    return yaml.safe_load((PERSONAS_DIR / f"{name}.yaml").read_text(encoding="utf-8"))


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", text).lower()


def persona_text_without_rules(name) -> str:
    """Whole file minus the shared RULES block (which names banned framings to forbid them)."""
    raw = (PERSONAS_DIR / f"{name}.yaml").read_text(encoding="utf-8")
    return normalise(raw.split("RULES (apply to every reply):")[0])


@pytest.mark.parametrize("name", NAMES)
def test_required_fields(name):
    cfg = load(name)
    assert cfg["agent_id"] == name
    for key in ("display_name", "model_tier", "temperature", "max_output_tokens",
                "tools", "triggers", "cooldown_seconds", "system_prompt"):
        assert key in cfg, f"{name} missing {key}"
    assert cfg["tools"] and cfg["cooldown_seconds"] > 0
    assert cfg["model_tier"] in ("standard", "light")
    assert "model" not in cfg, "model names come from env vars, not persona YAML"


@pytest.mark.parametrize("name", NAMES)
def test_no_banned_content(name):
    text = persona_text_without_rules(name)
    hits = [p for p in BANNED if re.search(p, text)]
    assert not hits, f"{name} contains banned terms: {hits}"


@pytest.mark.parametrize("name", NAMES)
def test_shared_safety_rules_present(name):
    prompt = normalise(load(name)["system_prompt"])
    assert "rules (apply to every reply)" in prompt
    for phrase in ("not a partner", "no romantic, flirtatious, possessive", "never invent",
                   "never guilt-trip", "lead with rest", "not a medical assessment",
                   "2 to 4 sentences"):
        assert phrase in prompt, f"{name} missing rule: {phrase}"


def test_personas_are_distinct():
    roles = {n: load(n)["system_prompt"].split("ROLE:")[1].split("\n")[0] for n in NAMES}
    assert len(set(roles.values())) == 5
