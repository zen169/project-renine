"""Confirmation gate for Renine.

Implements confirmation prompts for destructive and elevated operations.
No destructive action is ever executed without explicit user approval.

Inputs:
    - Action description and permission level.
    - config/security.yaml for always-confirm actions.

Outputs:
    - Confirmation result (approved/denied).
    - ConfirmationDeniedError if denied.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from renine.core.config import get_security_config
from renine.core.exceptions import ConfirmationDeniedError
from renine.core.logging_config import get_logger

logger = get_logger(__name__)


class ConfirmationStatus(Enum):
    """Status of a confirmation request."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    TIMED_OUT = "timed_out"


@dataclass
class ConfirmationRequest:
    """A pending confirmation request.

    Attributes:
        action: Short identifier for the action (e.g., "file_delete").
        description: Human-readable description of what will happen.
        source_agent: The agent requesting confirmation.
        status: Current confirmation status.
    """

    action: str
    description: str
    source_agent: str
    status: ConfirmationStatus = ConfirmationStatus.PENDING


def _load_always_confirm_actions() -> list[str]:
    """Load the list of actions that always require confirmation.

    Returns:
        List of action identifier strings.
    """
    config = get_security_config()
    confirmation_config = config.get("security", {}).get("confirmation", {})
    return confirmation_config.get("always_confirm", [])


def requires_confirmation(action: str) -> bool:
    """Check if an action requires user confirmation.

    Args:
        action: Action identifier (e.g., "file_delete").

    Returns:
        True if the action is in the always-confirm list.
    """
    always_confirm = _load_always_confirm_actions()
    return action in always_confirm


def request_confirmation(
    action: str,
    description: str,
    source_agent: str = "system",
) -> ConfirmationRequest:
    """Create a confirmation request for a destructive operation.

    In Phase 1, this creates the request object. The UI layer
    will be responsible for presenting it to the user and collecting
    the response.

    Args:
        action: Action identifier.
        description: Human-readable description of the action.
        source_agent: Name of the requesting agent.

    Returns:
        ConfirmationRequest in PENDING status.
    """
    request = ConfirmationRequest(
        action=action,
        description=description,
        source_agent=source_agent,
    )

    logger.warning(
        "confirmation_requested",
        action=action,
        description=description,
        source=source_agent,
    )

    return request


def approve(request: ConfirmationRequest) -> ConfirmationRequest:
    """Mark a confirmation request as approved.

    Args:
        request: The pending confirmation request.

    Returns:
        Updated request with APPROVED status.
    """
    request.status = ConfirmationStatus.APPROVED
    logger.info(
        "confirmation_approved",
        action=request.action,
        source=request.source_agent,
    )
    return request


def deny(request: ConfirmationRequest) -> ConfirmationRequest:
    """Mark a confirmation request as denied.

    Args:
        request: The pending confirmation request.

    Returns:
        Updated request with DENIED status.

    Raises:
        ConfirmationDeniedError: Always raised when a request is denied,
            to be caught by the calling tool/agent.
    """
    request.status = ConfirmationStatus.DENIED
    logger.warning(
        "confirmation_denied",
        action=request.action,
        source=request.source_agent,
    )
    raise ConfirmationDeniedError(
        f"User denied confirmation for action: {request.action} "
        f"({request.description})"
    )
