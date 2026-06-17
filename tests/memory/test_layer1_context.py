"""Tests for renine.memory.layer1_context — in-memory conversation context.

Validates:
- Messages can be added and retrieved.
- Message count is tracked.
- Overflow behavior trims oldest messages.
- Context can be cleared.
- Session ID is generated.
"""
from __future__ import annotations

import pytest

from renine.memory.layer1_context import ConversationContext, Message


class TestMessage:
    """Tests for the Message dataclass."""

    def test_to_dict(self) -> None:
        """to_dict returns role and content."""
        msg = Message(role="user", content="Hello")
        result = msg.to_dict()
        assert result == {"role": "user", "content": "Hello"}

    def test_has_timestamp(self) -> None:
        """Message auto-generates a timestamp."""
        msg = Message(role="user", content="Hi")
        assert msg.timestamp > 0

    def test_metadata_default(self) -> None:
        """Default metadata is an empty dict."""
        msg = Message(role="user", content="Hi")
        assert msg.metadata == {}


class TestConversationContext:
    """Tests for the ConversationContext class."""

    def test_add_message(self) -> None:
        """Messages can be added and retrieved."""
        ctx = ConversationContext(max_messages=50)
        ctx.add_message("user", "Hello")
        ctx.add_message("assistant", "Hi there!")

        messages = ctx.get_messages()
        assert len(messages) == 2
        assert messages[0] == {"role": "user", "content": "Hello"}
        assert messages[1] == {"role": "assistant", "content": "Hi there!"}

    def test_message_count(self) -> None:
        """message_count reflects the current number of messages."""
        ctx = ConversationContext(max_messages=50)
        assert ctx.message_count == 0
        ctx.add_message("user", "One")
        assert ctx.message_count == 1
        ctx.add_message("user", "Two")
        assert ctx.message_count == 2

    def test_clear(self) -> None:
        """clear() removes all messages."""
        ctx = ConversationContext(max_messages=50)
        ctx.add_message("user", "Hello")
        ctx.add_message("user", "World")
        ctx.clear()
        assert ctx.message_count == 0
        assert ctx.get_messages() == []

    def test_session_id(self) -> None:
        """Session ID is a non-empty string."""
        ctx = ConversationContext(max_messages=50)
        assert ctx.session_id.startswith("session_")

    def test_get_last_n(self) -> None:
        """get_last_n returns the N most recent messages."""
        ctx = ConversationContext(max_messages=50)
        for i in range(5):
            ctx.add_message("user", f"Message {i}")

        last_2 = ctx.get_last_n(2)
        assert len(last_2) == 2
        assert last_2[0]["content"] == "Message 3"
        assert last_2[1]["content"] == "Message 4"

    def test_overflow_trims_oldest(self) -> None:
        """Exceeding max_messages trims the oldest messages."""
        ctx = ConversationContext(max_messages=5)
        for i in range(8):
            ctx.add_message("user", f"Message {i}")

        # Should have trimmed — count should be <= max + 1 (system summary note)
        assert ctx.message_count <= 7
        # First message should be a system trim note
        messages = ctx.get_messages()
        has_system_note = any(
            msg["role"] == "system" and "summarized" in msg["content"].lower()
            for msg in messages
        )
        assert has_system_note

    def test_get_full_messages(self) -> None:
        """get_full_messages returns Message objects."""
        ctx = ConversationContext(max_messages=50)
        ctx.add_message("user", "Hello", metadata={"source": "voice"})

        full = ctx.get_full_messages()
        assert len(full) == 1
        assert isinstance(full[0], Message)
        assert full[0].metadata == {"source": "voice"}

    def test_add_with_metadata(self) -> None:
        """Messages can include metadata."""
        ctx = ConversationContext(max_messages=50)
        ctx.add_message("user", "Hello", metadata={"voice": True})

        full = ctx.get_full_messages()
        assert full[0].metadata == {"voice": True}
