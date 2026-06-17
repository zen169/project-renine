"""Layer 1 — Current Conversation Context for Renine.

In-memory conversation context that persists only for the duration
of a single conversation session. Messages are stored as a list
of role/content dictionaries compatible with LangGraph MessagesState.

When the message count reaches the configured maximum, the oldest
messages are summarized and dropped.

Inputs:
    - New messages to add (role + content).
    - config/settings.yaml for max_messages limit.

Outputs:
    - Current context as a list of message dicts.
    - Context is never serialized to disk.
    - Context is never sent to external APIs without sanitization.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from renine.core.config import get_settings
from renine.core.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class Message:
    """A single conversation message.

    Attributes:
        role: Message role ("user", "assistant", or "system").
        content: Message text content.
        timestamp: Unix timestamp of message creation.
        metadata: Optional additional context.
    """

    role: str
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, str]:
        """Convert to LLM-compatible message dict.

        Returns:
            Dictionary with "role" and "content" keys.
        """
        return {"role": self.role, "content": self.content}


class ConversationContext:
    """In-memory conversation context (Layer 1).

    Maintains a rolling window of conversation messages.
    When the limit is reached, oldest messages are dropped
    with a summary placeholder.

    This class is NOT thread-safe. In Phase 1, Renine processes
    one conversation at a time.
    """

    def __init__(self, max_messages: int | None = None) -> None:
        """Initialize the conversation context.

        Args:
            max_messages: Maximum number of messages to retain.
                          Defaults to config value (50).
        """
        if max_messages is None:
            settings = get_settings()
            max_messages = settings.get("memory", {}).get("layer1_max_messages", 50)

        self._max_messages: int = max_messages
        self._messages: list[Message] = []
        self._session_id: str = f"session_{int(time.time())}"

        logger.info(
            "context_initialized",
            session_id=self._session_id,
            max_messages=self._max_messages,
        )

    def add_message(self, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Add a message to the conversation context.

        If adding this message exceeds the limit, the oldest
        messages are dropped with a summary notice.

        Args:
            role: Message role ("user", "assistant", or "system").
            content: Message text content.
            metadata: Optional metadata dictionary.
        """
        message = Message(
            role=role,
            content=content,
            metadata=metadata or {},
        )
        self._messages.append(message)

        if len(self._messages) > self._max_messages:
            self._trim_oldest()

        logger.debug(
            "message_added",
            role=role,
            content_length=len(content),
            total_messages=len(self._messages),
        )

    def get_messages(self) -> list[dict[str, str]]:
        """Get all messages as LLM-compatible dicts.

        Returns:
            List of message dictionaries with "role" and "content".
        """
        return [msg.to_dict() for msg in self._messages]

    def get_full_messages(self) -> list[Message]:
        """Get all messages as full Message objects.

        Returns:
            List of Message dataclass instances.
        """
        return list(self._messages)

    def get_last_n(self, n: int) -> list[dict[str, str]]:
        """Get the last N messages.

        Args:
            n: Number of recent messages to return.

        Returns:
            List of the N most recent message dicts.
        """
        return [msg.to_dict() for msg in self._messages[-n:]]

    @property
    def message_count(self) -> int:
        """Return the current number of messages.

        Returns:
            Integer count of messages in context.
        """
        return len(self._messages)

    @property
    def session_id(self) -> str:
        """Return the current session identifier.

        Returns:
            String session ID.
        """
        return self._session_id

    def clear(self) -> None:
        """Clear all messages from the context."""
        count = len(self._messages)
        self._messages.clear()
        logger.info("context_cleared", cleared_count=count)

    def _trim_oldest(self) -> None:
        """Remove the oldest messages when the limit is exceeded.

        Drops the oldest half of messages and inserts a system
        message noting that earlier context was summarized.
        """
        trim_count = len(self._messages) // 4
        if trim_count < 1:
            trim_count = 1

        dropped = self._messages[:trim_count]
        self._messages = self._messages[trim_count:]

        # Insert a system note about dropped context
        summary_note = Message(
            role="system",
            content=(
                f"[{trim_count} earlier messages were summarized and removed "
                f"to maintain context window limits.]"
            ),
        )
        self._messages.insert(0, summary_note)

        logger.info(
            "context_trimmed",
            dropped_count=trim_count,
            remaining_count=len(self._messages),
        )
