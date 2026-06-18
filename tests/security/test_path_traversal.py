"""Tests for path traversal prevention and allowed/blocked path checks."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from renine.core.exceptions import InputValidationError
from renine.security.input_validator import validate_path


@pytest.fixture
def mock_sec_config():
    """Mock security settings for path testing."""
    config = {
        "security": {
            "filesystem": {
                "allowed_paths": [
                    "C:\\Users\\efren\\Downloads\\PROJECT RENINE V1.0"
                ],
                "blocked_paths": [
                    "C:\\Windows",
                    "C:\\Users\\efren\\Downloads\\PROJECT RENINE V1.0\\config"
                ],
                "max_read_size_bytes": 52428800,
            }
        }
    }
    with patch("renine.security.input_validator.get_security_config", return_value=config):
        yield config


def test_allowed_path_succeeds(mock_sec_config) -> None:
    """A path inside allowed_paths succeeds validation."""
    valid_path = "C:\\Users\\efren\\Downloads\\PROJECT RENINE V1.0\\renine\\tools"
    res = validate_path(valid_path)
    assert isinstance(res, Path)


def test_blocked_path_raises(mock_sec_config) -> None:
    """A path starting with a blocked path raises InputValidationError."""
    blocked_path = "C:\\Windows\\System32\\cmd.exe"
    with pytest.raises(InputValidationError, match="blocked by security policy"):
        validate_path(blocked_path)


def test_non_allowed_path_raises(mock_sec_config) -> None:
    """A path not inside allowed_paths raises InputValidationError."""
    unauthorized_path = "C:\\Users\\efren\\Desktop\\some_file.txt"
    with pytest.raises(InputValidationError, match="blocked \\(not within allowed paths\\)"):
        validate_path(unauthorized_path)


def test_path_traversal_blocked(mock_sec_config) -> None:
    """Attempted path traversal using relative components raises InputValidationError."""
    traversal_path = "C:\\Users\\efren\\Downloads\\PROJECT RENINE V1.0\\..\\..\\Windows"
    with pytest.raises(InputValidationError):
        validate_path(traversal_path)
