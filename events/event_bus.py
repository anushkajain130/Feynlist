"""
Event Bus
=========
Async publish/subscribe system for Feynlist events.

Events flow like this:
  Source (task toggle, timer, user message)
    → EventBus.publish(event)
      → Rules Engine evaluates all subscribed rules
        → Matching rules trigger agent invocations
          → Orchestrator routes to correct agent(s)

This replaces the old monolithic FLxCouncil trigger logic with a clean,
decoupled, testable event-driven architecture.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Callable, Awaitable

from loguru import logger

from core.models import AppEvent, EventType


# Type alias for event handlers
EventHandler = Callable[[AppEvent], Awaitable[None]]


class EventBus:
    """
    Async publish/subscribe event bus.
    Handlers are registered per EventType and called concurrently when an event fires.

    Example:
        bus = EventBus()

        @bus.subscribe(EventType.TASK_MISSED)
        async def on_task_missed(event: AppEvent):
            await orchestrator.dispatch(event)

        await bus.publish(AppEvent(event_type=EventType.TASK_MISSED, ...))
    """

    def __init__(self):
        self._handlers: dict[EventType, list[EventHandler]] = defaultdict(list)
        self._wildcard_handlers: list[EventHandler] = []

    # ------------------------------------------------------------------
    # SUBSCRIBE
    # ------------------------------------------------------------------

    def subscribe(
        self,
        event_type: EventType,
    ) -> Callable[[EventHandler], EventHandler]:
        """Decorator for subscribing to a specific event type."""
        def decorator(handler: EventHandler) -> EventHandler:
            self._handlers[event_type].append(handler)
            logger.debug(f"EventBus: subscribed {handler.__name__} → {event_type.value}")
            return handler
        return decorator

    def subscribe_handler(self, event_type: EventType, handler: EventHandler) -> None:
        """Register a handler programmatically (non-decorator version)."""
        self._handlers[event_type].append(handler)
        logger.debug(f"EventBus: registered handler for {event_type.value}")

    def subscribe_all(self, handler: EventHandler) -> None:
        """Register a handler that receives every event (wildcard)."""
        self._wildcard_handlers.append(handler)

    # ------------------------------------------------------------------
    # PUBLISH
    # ------------------------------------------------------------------

    async def publish(self, event: AppEvent) -> None:
        """
        Publish an event to all registered handlers.
        Handlers for the specific event type + wildcard handlers all run concurrently.
        Errors in individual handlers are caught and logged — one bad handler
        cannot break the rest.
        """
        handlers = self._handlers.get(event.event_type, []) + self._wildcard_handlers

        if not handlers:
            logger.debug(f"EventBus: no handlers for {event.event_type.value}")
            return

        logger.info(
            f"EventBus: publishing {event.event_type.value} "
            f"(payload_keys={list(event.payload.keys()) if event.payload else []})"
        )

        tasks = [self._safe_call(h, event) for h in handlers]
        await asyncio.gather(*tasks)

    async def _safe_call(self, handler: EventHandler, event: AppEvent) -> None:
        """Call a handler, catching and logging any exceptions."""
        try:
            await handler(event)
        except Exception as e:
            logger.error(
                f"EventBus: handler {handler.__name__} failed "
                f"for {event.event_type.value}: {e}"
            )

    # ------------------------------------------------------------------
    # DIAGNOSTICS
    # ------------------------------------------------------------------

    def registered_event_types(self) -> list[str]:
        return [e.value for e in self._handlers.keys()]

    def handler_count(self, event_type: EventType) -> int:
        return len(self._handlers.get(event_type, []))

    def __repr__(self) -> str:
        total = sum(len(v) for v in self._handlers.values()) + len(self._wildcard_handlers)
        return f"EventBus({total} handlers across {len(self._handlers)} event types)"


# Singleton
event_bus = EventBus()
