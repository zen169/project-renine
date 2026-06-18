"""Input validator for Renine.

Sanitizes and validates all external inputs (user text, file paths,
shell arguments) to prevent injection attacks, path traversal, and
malformed input.

Inputs:
    - Raw user input strings.
    - File paths for validation.
    - config/security.yaml for validation rules.

Outputs:
    - Validated and sanitized input, or InputValidationError.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from renine.core.config import get_security_config
from renine.core.exceptions import InputValidationError
from renine.core.logging_config import get_logger

logger = get_logger(__name__)


def _load_validation_config() -> dict[str, Any]:
    """Load input validation configuration from security.yaml.

    Returns:
        Validation rules dictionary.
    """
    config = get_security_config()
    return config.get("security", {}).get("input_validation", {})


def validate_text_input(text: str) -> str:
    """Validate and sanitize user text input.

    Checks for:
    - Empty input
    - Excessive length
    - Null bytes

    Args:
        text: Raw user input string.

    Returns:
        Sanitized text string.

    Raises:
        InputValidationError: If validation fails.
    """
    if not text or not text.strip():
        raise InputValidationError("Input cannot be empty.")

    # Remove null bytes
    text = text.replace("\x00", "")

    config = _load_validation_config()
    max_length = config.get("max_input_length", 10000)

    if len(text) > max_length:
        raise InputValidationError(
            f"Input exceeds maximum length of {max_length} characters."
        )

    return text.strip()


def validate_path(path_str: str) -> Path:
    """Validate a file path for safety.

    Checks for:
    - Path traversal attempts (../)
    - Blocked system directories
    - Excessive path depth

    Args:
        path_str: Raw path string to validate.

    Returns:
        Resolved, validated Path object.

    Raises:
        InputValidationError: If the path is unsafe.
    """
    config = _load_validation_config()
    security_config = get_security_config().get("security", {})
    fs_config = security_config.get("filesystem", {})

    # Resolve to absolute path
    path = Path(path_str).resolve()

    # Check path depth
    max_depth = config.get("max_path_depth", 15)
    if len(path.parts) > max_depth:
        raise InputValidationError(
            f"Path depth exceeds maximum of {max_depth} levels."
        )

    # Check against blocked paths
    blocked_paths = fs_config.get("blocked_paths", [])
    path_str_resolved = str(path).lower()
    for blocked in blocked_paths:
        if path_str_resolved.startswith(blocked.lower()):
            raise InputValidationError(
                f"Access to '{blocked}' is blocked by security policy."
            )

    # Check against allowed paths if configured
    allowed_paths = fs_config.get("allowed_paths", [])
    if allowed_paths:
        is_allowed = False
        for allowed_str in allowed_paths:
            allowed_path = Path(allowed_str).resolve()
            try:
                path.relative_to(allowed_path)
                is_allowed = True
                break
            except ValueError:
                # Fallback check for drive letter casing or absolute paths on Windows
                if str(path).lower().startswith(str(allowed_path).lower()):
                    is_allowed = True
                    break
        if not is_allowed:
            raise InputValidationError(
                f"Access to '{path_str}' is blocked (not within allowed paths)."
            )

    return path


def validate_shell_input(command: str) -> str:
    """Validate input that may be used in shell operations.

    Checks for dangerous shell metacharacters that could enable
    command injection.

    Args:
        command: Raw command or argument string.

    Returns:
        Validated command string.

    Raises:
        InputValidationError: If dangerous characters are detected.
    """
    config = _load_validation_config()
    blocked_chars = config.get("blocked_shell_chars", [])

    for char in blocked_chars:
        if char in command:
            raise InputValidationError(
                f"Shell input contains blocked character: '{char}'"
            )

    return command
