"""External LLM client for Renine.

Provides the interface to external LLM providers (e.g., Anthropic Claude)
as a fallback or high-capability option, enforcing strict data sanitization
and local fallback.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from renine.brain import ollama_client
from renine.core.config import get_settings
from renine.core.context_sanitizer import sanitize
from renine.core.exceptions import BrainError
from renine.core.logging_config import get_logger

logger = get_logger(__name__)


def generate_external_response(
    messages: list[dict[str, str]],
    model: str = "claude-3-5-sonnet-20241022",
    system_prompt: str | None = None,
    namespace: str = "external",
    **kwargs: Any,
) -> str:
    """Generate response using external LLM with strict sanitization and local fallback.

    Args:
        messages: List of message dicts with "role" and "content" keys.
        model: Model name for the external provider.
        system_prompt: Optional system prompt.
        namespace: The namespace context for this request.
        **kwargs: Additional provider arguments (e.g., temperature, max_tokens).

    Returns:
        The generated response string.

    Raises:
        SanitizationError: If the namespace is local-only.
        BrainError: If both external and fallback models fail.
    """
    settings = get_settings()
    fallback_enabled = settings.get("features", {}).get("external_llm_fallback", False)

    # 1. Build payload and force sanitization
    payload = {
        "messages": messages,
        "model": model,
        "system_prompt": system_prompt,
        "namespace": namespace,
        **kwargs,
    }
    
    # This will raise SanitizationError if namespace is local-only
    sanitized_payload = sanitize(payload)

    # If fallback is explicitly disabled, or we don't have an API key, fallback to local Ollama immediately
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not fallback_enabled or not api_key:
        logger.info(
            "external_llm_fallback_triggered",
            reason="fallback_disabled" if not fallback_enabled else "missing_api_key",
        )
        return ollama_client.chat(
            messages=sanitized_payload["messages"],
            system_prompt=sanitized_payload.get("system_prompt"),
        )

    # 2. Call Anthropic API
    try:
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        
        # Prepare the Anthropic request body
        body: dict[str, Any] = {
            "model": sanitized_payload["model"],
            "messages": sanitized_payload["messages"],
            "max_tokens": sanitized_payload.get("max_tokens", 1024),
        }
        if sanitized_payload.get("system_prompt"):
            body["system"] = sanitized_payload["system_prompt"]
        if "temperature" in sanitized_payload:
            body["temperature"] = sanitized_payload["temperature"]

        logger.info("sending_external_llm_request", model=model, namespace=namespace)
        
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=body,
            )
            response.raise_for_status()
            response_data = response.json()
            
            # Extract content from Anthropic response structure
            content_list = response_data.get("content", [])
            content = ""
            for item in content_list:
                if item.get("type") == "text":
                    content += item.get("text", "")
            
            logger.info("external_llm_request_success", model=model)
            return content

    except Exception as e:
        logger.warning(
            "external_llm_failed_falling_back",
            error=str(e),
            fallback_to_ollama=True,
        )
        try:
            return ollama_client.chat(
                messages=sanitized_payload["messages"],
                system_prompt=sanitized_payload.get("system_prompt"),
            )
        except Exception as fallback_err:
            logger.exception("local_ollama_fallback_failed")
            raise BrainError(
                f"External LLM failed ({e}) and fallback local Ollama also failed ({fallback_err})"
            ) from fallback_err
