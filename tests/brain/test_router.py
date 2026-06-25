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

    def test_routes_to_email_agent(self) -> None:
        """Keywords related to email route to the email agent."""
        decision = route("check my gmail inbox")
        assert decision.target == RouteTarget.EMAIL_AGENT

    def test_routes_to_news_agent(self) -> None:
        """Keywords related to news headlines route to the news agent."""
        decision = route("show tech news headlines")
        assert decision.target == RouteTarget.NEWS_AGENT

    def test_routes_to_browser_agent(self) -> None:
        """Keywords related to web browsing route to the browser agent."""
        decision = route("google standard time zone info")
        assert decision.target == RouteTarget.BROWSER_AGENT

