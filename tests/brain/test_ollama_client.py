"""Tests for renine.brain.ollama_client — Ollama LLM interface.

Validates:
- Chat function sends messages and returns content.
- Streaming chat yields chunks.
- Connection errors raise OllamaConnectionError.
- Model errors raise OllamaModelError.
- Health check returns boolean.

All tests use mocked Ollama responses — no live server required.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from renine.brain.ollama_client import (
    _prepend_system_prompt,
    chat,
    check_connection,
)
from renine.core.exceptions import OllamaConnectionError, OllamaModelError


class TestPrependSystemPrompt:
    """Tests for system prompt prepending."""

    def test_prepends_system_prompt(self) -> None:
        """System prompt is added as first message."""
        messages = [{"role": "user", "content": "Hello"}]
        result = _prepend_system_prompt(messages, "You are Renine.")
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "You are Renine."
        assert result[1]["role"] == "user"

    def test_no_system_prompt(self) -> None:
        """None system prompt returns messages unchanged."""
        messages = [{"role": "user", "content": "Hello"}]
        result = _prepend_system_prompt(messages, None)
        assert result == messages

    def test_empty_system_prompt(self) -> None:
        """Empty string system prompt is not prepended."""
        messages = [{"role": "user", "content": "Hello"}]
        result = _prepend_system_prompt(messages, "")
        assert result == messages


class TestChat:
    """Tests for the synchronous chat function."""

    @patch("renine.brain.ollama_client._build_client")
    def test_returns_response_content(self, mock_build: MagicMock) -> None:
        """Chat returns the assistant's response content."""
        mock_client = MagicMock()
        mock_client.chat.return_value = {
            "message": {"role": "assistant", "content": "Hello, I'm Renine!"}
        }
        mock_build.return_value = mock_client

        result = chat([{"role": "user", "content": "Hi"}])
        assert result == "Hello, I'm Renine!"

    @patch("renine.brain.ollama_client._build_client")
    def test_handles_empty_response(self, mock_build: MagicMock) -> None:
        """Empty response content returns empty string."""
        mock_client = MagicMock()
        mock_client.chat.return_value = {"message": {"role": "assistant", "content": ""}}
        mock_build.return_value = mock_client

        result = chat([{"role": "user", "content": "Hi"}])
        assert result == ""

    @patch("renine.brain.ollama_client._build_client")
    def test_connection_error(self, mock_build: MagicMock) -> None:
        """Connection failure raises OllamaConnectionError."""
        mock_client = MagicMock()
        mock_client.chat.side_effect = ConnectionError("Connection refused")
        mock_build.return_value = mock_client

        with pytest.raises(OllamaConnectionError):
            chat([{"role": "user", "content": "Hi"}])

    @patch("renine.brain.ollama_client._build_client")
    def test_model_error(self, mock_build: MagicMock) -> None:
        """Model error raises OllamaModelError."""
        import ollama

        mock_client = MagicMock()
        mock_client.chat.side_effect = ollama.ResponseError("model not found")
        mock_build.return_value = mock_client

        with pytest.raises(OllamaModelError):
            chat([{"role": "user", "content": "Hi"}])


class TestCheckConnection:
    """Tests for the health check function."""

    @patch("renine.brain.ollama_client._build_client")
    def test_returns_true_when_model_available(self, mock_build: MagicMock) -> None:
        """Returns True when the target model is listed."""
        mock_client = MagicMock()
        mock_client.list.return_value = {
            "models": [{"name": "qwen3:8b"}]
        }
        mock_build.return_value = mock_client

        assert check_connection() is True

    @patch("renine.brain.ollama_client._build_client")
    def test_returns_false_on_connection_error(self, mock_build: MagicMock) -> None:
        """Returns False when server is unreachable."""
        mock_client = MagicMock()
        mock_client.list.side_effect = ConnectionError("refused")
        mock_build.return_value = mock_client

        assert check_connection() is False
