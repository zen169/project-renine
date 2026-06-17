"""Tests for renine.core.config — YAML config loader.

Validates:
- Config loads correctly from YAML files.
- Missing config files raise FileNotFoundError.
- Environment variable interpolation works.
- Missing env vars resolve to defaults.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from renine.core.config import (
    _process_values,
    _resolve_env_vars,
    get_project_root,
    get_settings,
    load_yaml,
)


class TestResolveEnvVars:
    """Tests for ${VAR:-default} environment variable resolution."""

    def test_resolves_existing_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Existing env vars are substituted."""
        monkeypatch.setenv("TEST_HOST", "localhost")
        result = _resolve_env_vars("${TEST_HOST:-fallback}")
        assert result == "localhost"

    def test_resolves_to_default_when_missing(self) -> None:
        """Missing env vars resolve to the default value."""
        os.environ.pop("NONEXISTENT_VAR_12345", None)
        result = _resolve_env_vars("${NONEXISTENT_VAR_12345:-my_default}")
        assert result == "my_default"

    def test_resolves_without_default(self) -> None:
        """Missing env vars without defaults resolve to empty string."""
        os.environ.pop("NONEXISTENT_VAR_12345", None)
        result = _resolve_env_vars("${NONEXISTENT_VAR_12345}")
        assert result == ""

    def test_leaves_plain_strings_unchanged(self) -> None:
        """Strings without ${} patterns are returned unchanged."""
        result = _resolve_env_vars("plain_string")
        assert result == "plain_string"

    def test_multiple_vars_in_one_string(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Multiple ${} patterns in one string are all resolved."""
        monkeypatch.setenv("A_VAR", "hello")
        monkeypatch.setenv("B_VAR", "world")
        result = _resolve_env_vars("${A_VAR:-} ${B_VAR:-}")
        assert result == "hello world"


class TestProcessValues:
    """Tests for recursive value processing."""

    def test_processes_nested_dicts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env vars in nested dicts are resolved."""
        monkeypatch.setenv("NESTED_VAL", "resolved")
        data = {"a": {"b": "${NESTED_VAL:-fallback}"}}
        result = _process_values(data)
        assert result["a"]["b"] == "resolved"

    def test_processes_lists(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env vars in list items are resolved."""
        monkeypatch.setenv("LIST_VAL", "item")
        data = ["${LIST_VAL:-x}", "plain"]
        result = _process_values(data)
        assert result == ["item", "plain"]

    def test_preserves_non_strings(self) -> None:
        """Non-string values (int, bool, None) are preserved."""
        data = {"count": 42, "enabled": True, "nothing": None}
        result = _process_values(data)
        assert result == data


class TestLoadYaml:
    """Tests for YAML file loading."""

    def test_loads_existing_yaml(self) -> None:
        """settings.yaml loads without error."""
        result = load_yaml("settings.yaml")
        assert isinstance(result, dict)
        assert "app" in result or "ollama" in result

    def test_missing_file_raises_error(self) -> None:
        """Non-existent YAML file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_yaml("nonexistent_file.yaml")


class TestGetSettings:
    """Tests for the get_settings convenience function."""

    def test_returns_dict(self) -> None:
        """get_settings returns a dictionary."""
        result = get_settings()
        assert isinstance(result, dict)

    def test_contains_expected_keys(self) -> None:
        """Settings contain expected top-level keys."""
        result = get_settings()
        assert "ollama" in result


class TestGetProjectRoot:
    """Tests for project root resolution."""

    def test_returns_path(self) -> None:
        """get_project_root returns a Path object."""
        root = get_project_root()
        assert isinstance(root, Path)

    def test_root_contains_pyproject(self) -> None:
        """Project root contains pyproject.toml."""
        root = get_project_root()
        assert (root / "pyproject.toml").exists()
