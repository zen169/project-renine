"""Input router for Renine.

Routes incoming user input to the appropriate handler:
- Direct response for simple queries
- MainBrainAgent for conversation and planning
- Specialized agents via the brain's delegation system

In Phase 1, all inputs are routed to MainBrainAgent. Future phases
will add intent classification and agent delegation.

Inputs:
    - User text input (from chat or STT).
    - Current conversation context (Layer 1).

Outputs:
    - Routed to appropriate agent or direct response path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from renine.core.logging_config import get_logger

logger = get_logger(__name__)


class RouteTarget(Enum):
    """Possible routing destinations for user input."""

    MAIN_BRAIN = "main_brain"
    MEMORY_AGENT = "memory_agent"
    HOUSE_AGENT = "house_agent"
    INVENTORY_AGENT = "inventory_agent"
    PET_AGENT = "pet_agent"
    CALENDAR_AGENT = "calendar_agent"
    FILE_AGENT = "file_agent"
    CODING_AGENT = "coding_agent"
    SPREADSHEET_AGENT = "spreadsheet_agent"
    VISION_AGENT = "vision_agent"
    BROWSER_AGENT = "browser_agent"
    EMAIL_AGENT = "email_agent"
    NEWS_AGENT = "news_agent"
    SMART_HOME_AGENT = "smart_home_agent"
    DIRECT_RESPONSE = "direct_response"


@dataclass
class RouteDecision:
    """Result of the routing decision.

    Attributes:
        target: The agent or handler to route to.
        confidence: Routing confidence score (0.0 to 1.0).
        metadata: Additional routing context.
    """

    target: RouteTarget
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


def route(user_input: str, context: list[dict[str, str]] | None = None) -> RouteDecision:
    """Route user input to the appropriate handler.

    Routes input dynamically based on keywords for specialized agents
    in Phase 3, falling back to MainBrainAgent for conversation.

    Args:
        user_input: The user's text input.
        context: Optional conversation context for intent analysis.

    Returns:
        RouteDecision indicating where to send the input.
    """
    if not user_input or not user_input.strip():
        logger.debug("empty_input_received")
        return RouteDecision(
            target=RouteTarget.DIRECT_RESPONSE,
            confidence=1.0,
            metadata={"reason": "empty_input"},
        )

    query = user_input.lower().strip()

    # Phase 3 specialized routing rules
    if (
        "what can we cook" in query
        or "what to cook" in query
        or "list inventory" in query
        or "show inventory" in query
    ):
        logger.info("routing_to_inventory_agent", input=user_input)
        return RouteDecision(
            target=RouteTarget.INVENTORY_AGENT,
            confidence=1.0,
            metadata={"reason": "inventory_keywords"},
        )

    if (
        "what appliances are in" in query
        or "what items are in" in query
        or "what is in the" in query
        or "list house" in query
        or "show house" in query
    ):
        logger.info("routing_to_house_agent", input=user_input)
        return RouteDecision(
            target=RouteTarget.HOUSE_AGENT,
            confidence=1.0,
            metadata={"reason": "house_keywords"},
        )

    if "list pets" in query or "show pets" in query or "feed " in query:
        logger.info("routing_to_pet_agent", input=user_input)
        return RouteDecision(
            target=RouteTarget.PET_AGENT,
            confidence=1.0,
            metadata={"reason": "pet_keywords"},
        )

    # Phase 5 vision routing rules
    vision_keywords = (
        "screenshot",
        "take a screenshot",
        "capture screen",
        "ocr",
        "extract text from",
        "read text from",
        "describe image",
        "describe screen",
        "what do you see",
        "analyze image",
        "webcam",
        "camera",
        "list monitors",
        "show monitors",
    )
    if any(kw in query for kw in vision_keywords):
        logger.info("routing_to_vision_agent", input=user_input)
        return RouteDecision(
            target=RouteTarget.VISION_AGENT,
            confidence=1.0,
            metadata={"reason": "vision_keywords"},
        )

    # Phase 6 routing rules
    email_keywords = ("email", "inbox", "gmail", "draft", "compose")
    if any(kw in query for kw in email_keywords):
        logger.info("routing_to_email_agent", input=user_input)
        return RouteDecision(
            target=RouteTarget.EMAIL_AGENT,
            confidence=1.0,
            metadata={"reason": "email_keywords"},
        )

    news_keywords = ("headlines", "news", "rss feed", "fetch rss")
    if any(kw in query for kw in news_keywords):
        logger.info("routing_to_news_agent", input=user_input)
        return RouteDecision(
            target=RouteTarget.NEWS_AGENT,
            confidence=1.0,
            metadata={"reason": "news_keywords"},
        )

    browser_keywords = ("search web", "google", "wikipedia", "browse", "look up on the web", "web search", "go to webpage", "website")
    if any(kw in query for kw in browser_keywords):
        logger.info("routing_to_browser_agent", input=user_input)
        return RouteDecision(
            target=RouteTarget.BROWSER_AGENT,
            confidence=1.0,
            metadata={"reason": "browser_keywords"},
        )

    # Fallback to MainBrainAgent
    logger.info(
        "input_routed",
        target=RouteTarget.MAIN_BRAIN.value,
        input_length=len(user_input),
    )

    return RouteDecision(
        target=RouteTarget.MAIN_BRAIN,
        confidence=1.0,
        metadata={"phase": 6, "method": "default_routing"},
    )
