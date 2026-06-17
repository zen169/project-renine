"""Tests for renine.core.events — internal event bus."""
from __future__ import annotations

from renine.core.events import EventBus


class TestEventBus:
    """Tests for the EventBus class."""

    def setup_method(self) -> None:
        """Fresh bus for each test."""
        self.bus = EventBus()

    def test_subscribe_and_publish(self) -> None:
        """Published events reach subscribers."""
        received: list[dict] = []
        self.bus.subscribe("test.event", lambda p: received.append(p))
        self.bus.publish("test.event", {"key": "value"})
        assert received == [{"key": "value"}]

    def test_no_subscribers_no_error(self) -> None:
        """Publishing with no subscribers does not raise."""
        self.bus.publish("no.one.listening", {"data": 1})

    def test_multiple_subscribers(self) -> None:
        """All subscribers receive the event."""
        results: list[int] = []
        self.bus.subscribe("ev", lambda _: results.append(1))
        self.bus.subscribe("ev", lambda _: results.append(2))
        self.bus.publish("ev", {})
        assert results == [1, 2]

    def test_unsubscribe(self) -> None:
        """Unsubscribed handler does not receive events."""
        received: list[dict] = []
        handler = lambda p: received.append(p)  # noqa: E731
        self.bus.subscribe("ev", handler)
        self.bus.unsubscribe("ev", handler)
        self.bus.publish("ev", {"x": 1})
        assert received == []

    def test_handler_exception_does_not_propagate(self) -> None:
        """A handler that raises does not crash the publisher."""
        second: list[int] = []
        self.bus.subscribe("ev", lambda _: (_ for _ in ()).throw(ValueError("boom")))
        self.bus.subscribe("ev", lambda _: second.append(1))
        self.bus.publish("ev", {})  # Must not raise
        # Second handler still runs despite first failing
        assert second == [1]

    def test_clear(self) -> None:
        """clear() removes all subscribers."""
        self.bus.subscribe("ev", lambda _: None)
        self.bus.clear()
        assert self.bus.subscriber_count == 0

    def test_subscriber_count(self) -> None:
        """subscriber_count reflects registered handlers."""
        assert self.bus.subscriber_count == 0
        self.bus.subscribe("a", lambda _: None)
        self.bus.subscribe("b", lambda _: None)
        assert self.bus.subscriber_count == 2

    def test_none_payload_defaults_to_empty_dict(self) -> None:
        """None payload is treated as empty dict."""
        received: list[dict] = []
        self.bus.subscribe("ev", lambda p: received.append(p))
        self.bus.publish("ev", None)
        assert received == [{}]
