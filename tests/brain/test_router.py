"""Tests for renine.brain.router — input routing."""
from __future__ import annotations

from renine.brain.router import RouteDecision, RouteTarget, route


class TestRoute:
    """Tests for the route() function."""

    def test_non_empty_routes_to_main_brain(self) -> None:
        """Non-empty input routes to main_brain in Phase 1."""
        decision = route("Hello")
        assert decision.target == RouteTarget.MAIN_BRAIN

    def test_empty_input_routes_to_direct_response(self) -> None:
        """Empty string routes to direct response."""
        decision = route("")
        assert decision.target == RouteTarget.DIRECT_RESPONSE

    def test_whitespace_only_routes_to_direct_response(self) -> None:
        """Whitespace-only routes to direct response."""
        decision = route("   ")
        assert decision.target == RouteTarget.DIRECT_RESPONSE

    def test_returns_route_decision(self) -> None:
        """route() always returns a RouteDecision object."""
        decision = route("test")
        assert isinstance(decision, RouteDecision)

    def test_confidence_is_set(self) -> None:
        """RouteDecision has a confidence value."""
        decision = route("test")
        assert 0.0 <= decision.confidence <= 1.0

    def test_context_accepted(self) -> None:
        """route() accepts optional context without error."""
        ctx = [{"role": "user", "content": "hi"}]
        decision = route("Continue", context=ctx)
        assert decision.target == RouteTarget.MAIN_BRAIN
