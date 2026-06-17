"""Lightweight internal event bus for Renine.

Provides a simple publish/subscribe mechanism for decoupled inter-module
communication. Events are dispatched synchronously within the same process.

Usage:
    from renine.core.events import event_bus

    # Subscribe to an event
    event_bus.subscribe("voice.wake_word_detected", handle_wake_word)

    # Publish an event
    event_bus.publish("voice.wake_word_detected", {"timestamp": "..."})

Inputs:
    - Event name (string) and optional payload (dict).

Outputs:
    - Synchronous callback execution for all subscribers.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable

from renine.core.logging_config import get_logger

logger = get_logger(__name__)

# Type alias for event handler callbacks
EventHandler = Callable[[dict[str, Any]], None]


class EventBus:
    """Synchronous in-process event bus.

    Supports subscribe, unsubscribe, and publish operations.
    Handlers are called in registration order. Exceptions in
    handlers are logged but do not propagate to the publisher.
    """

    def __init__(self) -> None:
        """Initialize the event bus with an empty subscriber registry."""
        self._subscribers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        """Register a handler for a specific event.

        Args:
            event_name: Dot-separated event identifier
                        (e.g., "voice.wake_word_detected").
            handler: Callable that accepts a dict payload.
        """
        self._subscribers[event_name].append(handler)
        logger.debug(
            "event_subscribed",
            ev=event_name,
            handler=handler.__qualname__,
        )

    def unsubscribe(self, event_name: str, handler: EventHandler) -> None:
        """Remove a handler from a specific event.

        Args:
            event_name: Dot-separated event identifier.
            handler: Previously registered callable to remove.
        """
        handlers = self._subscribers.get(event_name, [])
        if handler in handlers:
            handlers.remove(handler)
            logger.debug(
                "event_unsubscribed",
                ev=event_name,
                handler=handler.__qualname__,
            )

    def publish(self, event_name: str, payload: dict[str, Any] | None = None) -> None:
        """Publish an event to all registered handlers.

        Handlers are called synchronously in registration order.
        Exceptions in individual handlers are caught and logged —
        they do not prevent other handlers from executing.

        Args:
            event_name: Dot-separated event identifier.
            payload: Optional data dictionary passed to each handler.
        """
        if payload is None:
            payload = {}

        handlers = self._subscribers.get(event_name, [])
        if not handlers:
            return

        logger.debug(
            "event_published",
            ev=event_name,
            handler_count=len(handlers),
        )

        for handler in handlers:
            try:
                handler(payload)
            except Exception:
                logger.exception(
                    "event_handler_error",
                    ev=event_name,
                    handler=handler.__qualname__,
                )

    def clear(self) -> None:
        """Remove all subscribers from all events."""
        self._subscribers.clear()
        logger.debug("event_bus_cleared")

    @property
    def subscriber_count(self) -> int:
        """Return total number of registered handlers across all events.

        Returns:
            Total subscriber count.
        """
        return sum(len(handlers) for handlers in self._subscribers.values())


# Global singleton — all modules import and use this instance
event_bus = EventBus()
