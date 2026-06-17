"""Tests for renine.core.context_sanitizer — sensitive data stripping.

Validates:
- Sensitive keys are stripped from payloads.
- Safe keys are preserved.
- Local-only namespaces are blocked.
- Nested sensitive fields are found and redacted.
"""
from __future__ import annotations

import pytest

from renine.core.context_sanitizer import check_namespace, sanitize
from renine.core.exceptions import SanitizationError


class TestSanitize:
    """Tests for the sanitize function."""

    def test_strips_sensitive_fields(self) -> None:
        """Known sensitive fields are replaced with [REDACTED]."""
        payload = {
            "message": "Hello",
            "password": "secret123",
            "api_key": "sk-abc",
        }
        result = sanitize(payload)
        assert result["message"] == "Hello"
        assert result["password"] == "[REDACTED]"
        assert result["api_key"] == "[REDACTED]"

    def test_preserves_safe_fields(self) -> None:
        """Non-sensitive fields are passed through unchanged."""
        payload = {
            "message": "Hello world",
            "role": "user",
            "timestamp": 12345,
        }
        result = sanitize(payload)
        assert result["message"] == "Hello world"
        assert result["role"] == "user"
        assert result["timestamp"] == 12345

    def test_handles_nested_dicts(self) -> None:
        """Sensitive fields in nested dicts are also stripped."""
        payload = {
            "user": {
                "name": "Efren",
                "token": "abc123",
            }
        }
        result = sanitize(payload)
        assert result["user"]["name"] == "Efren"
        assert result["user"]["token"] == "[REDACTED]"

    def test_handles_lists_of_dicts(self) -> None:
        """Sensitive fields in list items are stripped."""
        payload = {
            "items": [
                {"name": "item1", "secret": "hidden"},
                {"name": "item2", "data": "safe"},
            ]
        }
        result = sanitize(payload)
        assert result["items"][0]["secret"] == "[REDACTED]"
        assert result["items"][1]["data"] == "safe"

    def test_does_not_mutate_original(self) -> None:
        """Original payload is not modified (deep copy)."""
        payload = {"password": "original"}
        sanitize(payload)
        assert payload["password"] == "original"

    def test_empty_payload(self) -> None:
        """Empty dict is handled without error."""
        result = sanitize({})
        assert result == {}


class TestCheckNamespace:
    """Tests for the check_namespace function."""

    def test_blocks_local_only_namespace(self) -> None:
        """Local-only namespaces raise SanitizationError."""
        with pytest.raises(SanitizationError):
            check_namespace("mind")

    def test_blocks_personality_namespace(self) -> None:
        """Personality namespace is also blocked."""
        with pytest.raises(SanitizationError):
            check_namespace("personality")

    def test_allows_non_local_namespace(self) -> None:
        """Non-restricted namespaces pass without error."""
        # "general" is not in the local-only list
        check_namespace("general")

    def test_case_insensitive(self) -> None:
        """Namespace check is case-insensitive."""
        with pytest.raises(SanitizationError):
            check_namespace("MIND")


class TestSanitizeWithNamespace:
    """Tests for sanitize with namespace-bearing payloads."""

    def test_blocks_payload_with_local_namespace(self) -> None:
        """Payloads with local-only namespace key are blocked."""
        payload = {"namespace": "inventory", "data": "stuff"}
        with pytest.raises(SanitizationError):
            sanitize(payload)

    def test_allows_payload_without_namespace(self) -> None:
        """Payloads without namespace key pass through."""
        payload = {"message": "Hello"}
        result = sanitize(payload)
        assert result["message"] == "Hello"
