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

    In Phase 1, all inputs are routed to MainBrainAgent.
    Future phases will implement intent classification here.

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

    # Phase 1: All non-empty inputs go to MainBrainAgent
    logger.info(
        "input_routed",
        target=RouteTarget.MAIN_BRAIN.value,
        input_length=len(user_input),
    )

    return RouteDecision(
        target=RouteTarget.MAIN_BRAIN,
        confidence=1.0,
        metadata={"phase": 1, "method": "default_routing"},
    )
