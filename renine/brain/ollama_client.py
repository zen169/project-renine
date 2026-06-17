"""Ollama client for Renine.

Provides the interface to Qwen3 8B served locally via Ollama.
Supports both streaming and non-streaming chat completions.

Inputs:
    - Messages list (LangChain-compatible format).
    - config/settings.yaml for host, model, and timeout settings.

Outputs:
    - Complete response string or async stream of response chunks.
"""
from __future__ import annotations

import asyncio
from typing import Any, AsyncGenerator

import ollama

from renine.core.config import get_settings
from renine.core.exceptions import OllamaConnectionError, OllamaModelError
from renine.core.logging_config import get_logger

logger = get_logger(__name__)


def _get_ollama_config() -> dict[str, Any]:
    """Extract Ollama-specific configuration from settings.

    Returns:
        Dictionary with host, model, timeout, and retry settings.
    """
    settings = get_settings()
    return settings.get("ollama", {})


def _build_client(host: str | None = None) -> ollama.Client:
    """Create an Ollama client instance.

    Args:
        host: Ollama server URL. Defaults to config value.

    Returns:
        Configured Ollama client.
    """
    config = _get_ollama_config()
    target_host = host or config.get("host", "http://localhost:11434")
    return ollama.Client(host=target_host)


def _build_async_client(host: str | None = None) -> ollama.AsyncClient:
    """Create an async Ollama client instance.

    Args:
        host: Ollama server URL. Defaults to config value.

    Returns:
        Configured async Ollama client.
    """
    config = _get_ollama_config()
    target_host = host or config.get("host", "http://localhost:11434")
    return ollama.AsyncClient(host=target_host)


def chat(
    messages: list[dict[str, str]],
    model: str | None = None,
    system_prompt: str | None = None,
) -> str:
    """Send a synchronous chat request to Ollama.

    Args:
        messages: List of message dicts with "role" and "content" keys.
        model: Model name override. Defaults to config value.
        system_prompt: Optional system prompt prepended to messages.

    Returns:
        The assistant's response content string.

    Raises:
        OllamaConnectionError: If Ollama server is unreachable.
        OllamaModelError: If the requested model is not available.
    """
    config = _get_ollama_config()
    target_model = model or config.get("model", "qwen3:8b")

    full_messages = _prepend_system_prompt(messages, system_prompt)

    try:
        client = _build_client()
        response = client.chat(model=target_model, messages=full_messages)
        content = response.get("message", {}).get("content", "")
        logger.info(
            "ollama_chat_complete",
            model=target_model,
            message_count=len(full_messages),
            response_length=len(content),
        )
        return content

    except ollama.ResponseError as e:
        logger.error("ollama_model_error", model=target_model, error=str(e))
        raise OllamaModelError(str(e)) from e
    except Exception as e:
        logger.error("ollama_connection_error", error=str(e))
        raise OllamaConnectionError(str(e)) from e


async def chat_stream(
    messages: list[dict[str, str]],
    model: str | None = None,
    system_prompt: str | None = None,
) -> AsyncGenerator[str, None]:
    """Send a streaming chat request to Ollama.

    Yields response content chunks as they arrive from the model.

    Args:
        messages: List of message dicts with "role" and "content" keys.
        model: Model name override. Defaults to config value.
        system_prompt: Optional system prompt prepended to messages.

    Yields:
        String chunks of the assistant's response.

    Raises:
        OllamaConnectionError: If Ollama server is unreachable.
        OllamaModelError: If the requested model is not available.
    """
    config = _get_ollama_config()
    target_model = model or config.get("model", "qwen3:8b")

    full_messages = _prepend_system_prompt(messages, system_prompt)

    try:
        client = _build_async_client()
        stream = await client.chat(
            model=target_model,
            messages=full_messages,
            stream=True,
        )

        total_length = 0
        async for chunk in stream:
            content = chunk.get("message", {}).get("content", "")
            if content:
                total_length += len(content)
                yield content

        logger.info(
            "ollama_stream_complete",
            model=target_model,
            total_length=total_length,
        )

    except ollama.ResponseError as e:
        logger.error("ollama_model_error", model=target_model, error=str(e))
        raise OllamaModelError(str(e)) from e
    except Exception as e:
        logger.error("ollama_connection_error", error=str(e))
        raise OllamaConnectionError(str(e)) from e


def _prepend_system_prompt(
    messages: list[dict[str, str]],
    system_prompt: str | None,
) -> list[dict[str, str]]:
    """Prepend a system prompt to the messages list if provided.

    Args:
        messages: Original messages list.
        system_prompt: System prompt text, or None to skip.

    Returns:
        Messages list with system prompt prepended (if provided).
    """
    if not system_prompt:
        return messages

    system_message = {"role": "system", "content": system_prompt}
    return [system_message, *messages]


def check_connection() -> bool:
    """Verify that the Ollama server is reachable and the model is available.

    Returns:
        True if connection is healthy and model exists.
    """
    try:
        client = _build_client()
        models = client.list()
        config = _get_ollama_config()
        target_model = config.get("model", "qwen3:8b")

        available = [m.get("name", "") for m in models.get("models", [])]
        is_available = any(target_model in name for name in available)

        logger.info(
            "ollama_health_check",
            connected=True,
            model_available=is_available,
            target_model=target_model,
        )
        return is_available

    except Exception as e:
        logger.error("ollama_health_check_failed", error=str(e))
        return False
