"""Tests for renine.brain.external_client — External LLM API client.

Validates:
- Calls to local-only namespaces are blocked by SanitizationError.
- Calls with fallback disabled route to local Ollama client.
- Successful API call returns generated text content.
- Failed API calls fall back to local Ollama.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from renine.brain.external_client import generate_external_response
from renine.core.exceptions import SanitizationError


@pytest.fixture
def mock_settings() -> dict:
    """Default settings dictionary mock."""
    return {
        "features": {
            "external_llm_fallback": True,
        }
    }


class TestExternalClient:
    """Tests for the external client interface."""

    @patch("renine.brain.external_client.get_settings")
    def test_blocks_local_only_namespaces(self, mock_get_settings: MagicMock) -> None:
        """Any request originating from local-only namespace is blocked."""
        # 'mind' is a local-only namespace in config/security.yaml
        messages = [{"role": "user", "content": "What is in my room?"}]
        with pytest.raises(SanitizationError):
            generate_external_response(
                messages=messages,
                namespace="mind",
            )

    @patch("renine.brain.external_client.ollama_client.chat")
    @patch("renine.brain.external_client.get_settings")
    def test_routes_to_ollama_if_fallback_disabled(
        self, mock_get_settings: MagicMock, mock_ollama_chat: MagicMock
    ) -> None:
        """If external_llm_fallback is disabled, falls back to Ollama."""
        mock_get_settings.return_value = {
            "features": {"external_llm_fallback": False}
        }
        mock_ollama_chat.return_value = "Ollama response"

        messages = [{"role": "user", "content": "Hello"}]
        result = generate_external_response(messages=messages)
        
        assert result == "Ollama response"
        mock_ollama_chat.assert_called_once()

    @patch("renine.brain.external_client.ollama_client.chat")
    @patch("renine.brain.external_client.get_settings")
    @patch.dict(os.environ, {}, clear=True)
    def test_routes_to_ollama_if_no_api_key(
        self, mock_get_settings: MagicMock, mock_ollama_chat: MagicMock
    ) -> None:
        """If ANTHROPIC_API_KEY is missing, falls back to Ollama."""
        mock_get_settings.return_value = {
            "features": {"external_llm_fallback": True}
        }
        mock_ollama_chat.return_value = "Ollama response"

        messages = [{"role": "user", "content": "Hello"}]
        result = generate_external_response(messages=messages)
        
        assert result == "Ollama response"
        mock_ollama_chat.assert_called_once()

    @patch("renine.brain.external_client.httpx.Client")
    @patch("renine.brain.external_client.get_settings")
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_successful_external_llm_call(
        self, mock_get_settings: MagicMock, mock_client_class: MagicMock
    ) -> None:
        """A successful Anthropic API call parses and returns the text response."""
        mock_get_settings.return_value = {
            "features": {"external_llm_fallback": True}
        }

        # Mock the client context manager and post method
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "content": [{"type": "text", "text": "Claude response"}]
        }
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client

        messages = [{"role": "user", "content": "Hello"}]
        result = generate_external_response(messages=messages)
        
        assert result == "Claude response"
        mock_client.post.assert_called_once()

    @patch("renine.brain.external_client.httpx.Client")
    @patch("renine.brain.external_client.ollama_client.chat")
    @patch("renine.brain.external_client.get_settings")
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_falls_back_on_api_error(
        self,
        mock_get_settings: MagicMock,
        mock_ollama_chat: MagicMock,
        mock_client_class: MagicMock,
    ) -> None:
        """If the external API request fails, we fall back to local Ollama."""
        mock_get_settings.return_value = {
            "features": {"external_llm_fallback": True}
        }
        mock_ollama_chat.return_value = "Ollama fallback response"

        # Mock client post raising an error
        mock_client = MagicMock()
        mock_client.post.side_effect = Exception("API connection timeout")
        mock_client_class.return_value.__enter__.return_value = mock_client

        messages = [{"role": "user", "content": "Hello"}]
        result = generate_external_response(messages=messages)
        
        assert result == "Ollama fallback response"
        mock_ollama_chat.assert_called_once()
