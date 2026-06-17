"""Response builder for Renine.

Assembles the final response object that is sent to the UI layer.
Handles formatting, metadata attachment, and response type classification.

Inputs:
    - Raw response content from agents or direct LLM calls.
    - Metadata (source agent, timing, tool results, etc.).

Outputs:
    - Structured RenineResponse object for the UI/TTS pipeline.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from renine.core.logging_config import get_logger

logger = get_logger(__name__)


class ResponseType(Enum):
    """Classification of response types."""

    TEXT = "text"
    VOICE = "voice"
    ERROR = "error"
    CONFIRMATION_REQUEST = "confirmation_request"
    TOOL_RESULT = "tool_result"
    SYSTEM = "system"


@dataclass
class RenineResponse:
    """Structured response object for the Renine system.

    Attributes:
        content: The response text content.
        response_type: Classification of the response.
        source_agent: Name of the agent that generated this response.
        timestamp: Unix timestamp of response creation.
        metadata: Additional response context.
        speak: Whether this response should be spoken via TTS.
        tool_results: Results from any tools that were executed.
    """

    content: str
    response_type: ResponseType = ResponseType.TEXT
    source_agent: str = "main_brain"
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    speak: bool = True
    tool_results: list[dict[str, Any]] = field(default_factory=list)


def build_text_response(
    content: str,
    source_agent: str = "main_brain",
    speak: bool = True,
    metadata: dict[str, Any] | None = None,
) -> RenineResponse:
    """Build a standard text response.

    Args:
        content: Response text content.
        source_agent: Name of the originating agent.
        speak: Whether TTS should speak this response.
        metadata: Optional metadata dictionary.

    Returns:
        Assembled RenineResponse.
    """
    response = RenineResponse(
        content=content,
        response_type=ResponseType.TEXT,
        source_agent=source_agent,
        speak=speak,
        metadata=metadata or {},
    )
    logger.info(
        "response_built",
        type=ResponseType.TEXT.value,
        source=source_agent,
        length=len(content),
    )
    return response


def build_error_response(
    error_message: str,
    source_agent: str = "system",
    user_friendly: str | None = None,
) -> RenineResponse:
    """Build an error response with user-friendly messaging.

    Args:
        error_message: Technical error description (logged only).
        source_agent: Name of the agent where the error occurred.
        user_friendly: User-facing error message. If None, a generic
                       message is used.

    Returns:
        Assembled RenineResponse with error type.
    """
    display_message = user_friendly or (
        "I encountered an issue processing that. Could you try again?"
    )

    response = RenineResponse(
        content=display_message,
        response_type=ResponseType.ERROR,
        source_agent=source_agent,
        speak=True,
        metadata={"technical_error": error_message},
    )
    logger.error(
        "error_response_built",
        source=source_agent,
        error=error_message,
    )
    return response


def build_confirmation_response(
    prompt: str,
    action_description: str,
    source_agent: str = "system",
) -> RenineResponse:
    """Build a confirmation request response.

    Used when a destructive operation requires user approval.

    Args:
        prompt: The confirmation question to display.
        action_description: Description of the pending action.
        source_agent: Name of the requesting agent.

    Returns:
        Assembled RenineResponse with confirmation type.
    """
    response = RenineResponse(
        content=prompt,
        response_type=ResponseType.CONFIRMATION_REQUEST,
        source_agent=source_agent,
        speak=True,
        metadata={"pending_action": action_description},
    )
    logger.info(
        "confirmation_requested",
        source=source_agent,
        action=action_description,
    )
    return response


def build_tool_result_response(
    content: str,
    tool_results: list[dict[str, Any]],
    source_agent: str = "main_brain",
) -> RenineResponse:
    """Build a response that includes tool execution results.

    Args:
        content: Summary text describing the tool results.
        tool_results: List of tool result dictionaries.
        source_agent: Name of the agent that invoked the tools.

    Returns:
        Assembled RenineResponse with tool results attached.
    """
    response = RenineResponse(
        content=content,
        response_type=ResponseType.TOOL_RESULT,
        source_agent=source_agent,
        speak=True,
        tool_results=tool_results,
    )
    logger.info(
        "tool_result_response_built",
        source=source_agent,
        tool_count=len(tool_results),
    )
    return response
