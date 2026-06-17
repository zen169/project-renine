"""Tests for renine.security.input_validator — input sanitization."""
from __future__ import annotations

import pytest

from renine.core.exceptions import InputValidationError
from renine.security.input_validator import (
    validate_shell_input,
    validate_text_input,
)


class TestValidateTextInput:
    """Tests for validate_text_input."""

    def test_valid_input_returned(self) -> None:
        """Valid text is returned stripped."""
        assert validate_text_input("  Hello  ") == "Hello"

    def test_empty_raises(self) -> None:
        """Empty string raises InputValidationError."""
        with pytest.raises(InputValidationError):
            validate_text_input("")

    def test_whitespace_only_raises(self) -> None:
        """Whitespace-only raises InputValidationError."""
        with pytest.raises(InputValidationError):
            validate_text_input("   ")

    def test_null_bytes_removed(self) -> None:
        """Null bytes are stripped from input."""
        result = validate_text_input("hello\x00world")
        assert "\x00" not in result
        assert "helloworld" in result

    def test_too_long_raises(self) -> None:
        """Input exceeding max length raises InputValidationError."""
        with pytest.raises(InputValidationError):
            validate_text_input("x" * 100_001)


class TestValidateShellInput:
    """Tests for validate_shell_input."""

    def test_safe_input_returned(self) -> None:
        """Safe input is returned unchanged."""
        result = validate_shell_input("safe_argument")
        assert result == "safe_argument"

    def test_semicolon_blocked(self) -> None:
        """Semicolons are blocked."""
        with pytest.raises(InputValidationError):
            validate_shell_input("arg; rm -rf /")

    def test_pipe_blocked(self) -> None:
        """Pipe character is blocked."""
        with pytest.raises(InputValidationError):
            validate_shell_input("arg | cat /etc/passwd")

    def test_backtick_blocked(self) -> None:
        """Backtick is blocked."""
        with pytest.raises(InputValidationError):
            validate_shell_input("`whoami`")
