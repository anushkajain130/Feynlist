"""
Behavioral Rules Engine
=======================
Evaluates events against defined rules to decide whether and how to
trigger agent responses. This is the intelligence layer between raw events
and the orchestrator.

Rules are simple data objects: condition → action.
The engine evaluates all matching rules for each event.

This replaces the scattered if/elif trigger logic in the old FLxCouncil.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Awaitable, Optional

from loguru import logger

from core.models import AppEvent, EventType, AgentId


# Type for rule conditions
Condition = Callable[[AppEvent], bool]
# Type for rule actions (called when condition is met)
Action = Callable[[AppEvent], Awaitable[None]]


@dataclass
class Rule:
    """A single behavioral rule."""
    name: str
    event_type: EventType
    condition: Condition                    # Returns True if rule should fire
    action: Action                          # Called when condition passes
    priority: int = 0                       # Higher = evaluated first
    description: str = ""
    enabled: bool = True


class RulesEngine:
    """
    Evaluates all registered rules for incoming events.
    Rules with the same event_type are sorted by priority (descending).
    """

    def __init__(self):
        self._rules: list[Rule] = []

    def register(self, rule: Rule) -> None:
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority, reverse=True)
        logger.debug(f"RulesEngine: registered rule '{rule.name}' for {rule.event_type.value}")

    async def evaluate(self, event: AppEvent) -> int:
        """
        Evaluate all rules for the given event.
        Returns the number of rules that fired.
        """
        matching = [
            r for r in self._rules
            if r.enabled and r.event_type == event.event_type
        ]

        if not matching:
            return 0

        fired = 0
        for rule in matching:
            try:
                if rule.condition(event):
                    logger.info(f"RulesEngine: rule '{rule.name}' fired.")
                    await rule.action(event)
                    fired += 1
            except Exception as e:
                logger.error(f"RulesEngine: rule '{rule.name}' failed: {e}")

        return fired

    def enable(self, rule_name: str) -> None:
        for r in self._rules:
            if r.name == rule_name:
                r.enabled = True

    def disable(self, rule_name: str) -> None:
        for r in self._rules:
            if r.name == rule_name:
                r.enabled = False

    def list_rules(self) -> list[dict]:
        return [
            {
                "name": r.name,
                "event": r.event_type.value,
                "priority": r.priority,
                "enabled": r.enabled,
                "description": r.description,
            }
            for r in self._rules
        ]


# Singleton
rules_engine = RulesEngine()


# =============================================================================
# DEFAULT RULES REGISTRATION
# =============================================================================

def register_default_rules(orchestrator) -> None:
    """
    Register all default behavioral rules.
    Called once at application startup after orchestrator is initialized.
    """
    from core.models import AppEvent

    # Rule: Task missed → Freya calls it out
    rules_engine.register(Rule(
        name="task_missed_freya",
        event_type=EventType.TASK_MISSED,
        condition=lambda e: bool((e.payload or {}).get("task_name")),
        action=lambda e: orchestrator.dispatch(e),
        priority=10,
        description="Freya responds when a task is missed.",
    ))

    # Rule: Streak broken → Anya responds
    rules_engine.register(Rule(
        name="streak_broken_anya",
        event_type=EventType.STREAK_BROKEN,
        condition=lambda e: True,
        action=lambda e: orchestrator.dispatch(e),
        priority=9,
        description="Anya responds when the streak breaks.",
    ))

    # Rule: Burnout detected → Anya takes lead
    rules_engine.register(Rule(
        name="burnout_anya",
        event_type=EventType.BURNOUT_DETECTED,
        condition=lambda e: (e.payload or {}).get("severity") in ("moderate", "severe"),
        action=lambda e: orchestrator.dispatch(e),
        priority=10,
        description="Anya responds to burnout signals.",
    ))

    # Rule: Task completed → Albedo celebrates
    rules_engine.register(Rule(
        name="task_completed_albedo",
        event_type=EventType.TASK_COMPLETED,
        condition=lambda e: True,
        action=lambda e: orchestrator.dispatch(e),
        priority=5,
        description="Albedo responds when a task is completed.",
    ))

    # Rule: Scheduled checkin → ZeroTwo reviews
    rules_engine.register(Rule(
        name="checkin_zerotwo",
        event_type=EventType.SCHEDULED_CHECKIN,
        condition=lambda e: True,
        action=lambda e: orchestrator.dispatch(e),
        priority=5,
        description="ZeroTwo reviews performance at scheduled intervals.",
    ))

    # Rule: Day start → Freya looks at the day's plan
    rules_engine.register(Rule(
        name="day_start_freya",
        event_type=EventType.DAY_START,
        condition=lambda e: True,
        action=lambda e: orchestrator.dispatch(e),
        priority=5,
        description="Freya opens the day.",
    ))

    # Rule: End of day → Anya gives a short review
    rules_engine.register(Rule(
        name="day_end_review_anya",
        event_type=EventType.DAY_END_REVIEW,
        condition=lambda e: True,
        action=lambda e: orchestrator.dispatch(e),
        priority=6,
        description="Anya reviews the day.",
    ))

    # Rule: Streak milestone → Albedo celebrates
    rules_engine.register(Rule(
        name="streak_milestone_albedo",
        event_type=EventType.STREAK_MILESTONE,
        condition=lambda e: True,
        action=lambda e: orchestrator.dispatch(e),
        priority=5,
        description="Albedo celebrates a streak milestone.",
    ))

    # Rule: User direct message → route based on @mention or default
    rules_engine.register(Rule(
        name="user_message_route",
        event_type=EventType.USER_DIRECT_MESSAGE,
        condition=lambda e: bool((e.payload or {}).get("message")),
        action=lambda e: orchestrator.dispatch(e),
        priority=10,
        description="Route user messages to the appropriate agent.",
    ))

    logger.info(f"RulesEngine: {len(rules_engine._rules)} default rules registered.")
