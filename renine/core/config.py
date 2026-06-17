"""Configuration loader for Renine.

Reads YAML configuration files from the config/ directory and provides
a typed, centralized interface for all modules to access settings.
Environment variable interpolation is supported via ${VAR:-default} syntax.

Inputs:
    - YAML files in config/ directory
    - Environment variables for secret interpolation

Outputs:
    - Typed configuration dataclass accessible via get_settings()
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml


# Pattern to match ${ENV_VAR:-default_value} in YAML values
_ENV_VAR_PATTERN = re.compile(r"\$\{([^}^{]+)\}")

# Project root is two levels up from this file (renine/core/config.py -> project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CONFIG_DIR = _PROJECT_ROOT / "config"


def _resolve_env_vars(value: str) -> str:
    """Replace ${VAR:-default} patterns with environment variable values.

    Args:
        value: String potentially containing ${VAR:-default} patterns.

    Returns:
        String with all environment variable references resolved.
    """
    def _replace_match(match: re.Match[str]) -> str:
        expr = match.group(1)
        if ":-" in expr:
            var_name, default = expr.split(":-", 1)
        else:
            var_name, default = expr, ""
        return os.environ.get(var_name, default)

    return _ENV_VAR_PATTERN.sub(_replace_match, value)


def _process_values(data: Any) -> Any:
    """Recursively resolve environment variables in all string values.

    Args:
        data: Configuration data (dict, list, or scalar).

    Returns:
        Data with all string values having env vars resolved.
    """
    if isinstance(data, dict):
        return {k: _process_values(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_process_values(item) for item in data]
    if isinstance(data, str):
        return _resolve_env_vars(data)
    return data


def load_yaml(filename: str) -> dict[str, Any]:
    """Load and parse a YAML configuration file with env var interpolation.

    Args:
        filename: Name of the YAML file in the config/ directory
                  (e.g., "settings.yaml").

    Returns:
        Parsed configuration dictionary with env vars resolved.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        yaml.YAMLError: If the file contains invalid YAML.
    """
    filepath = _CONFIG_DIR / filename
    if not filepath.exists():
        msg = f"Configuration file not found: {filepath}"
        raise FileNotFoundError(msg)

    with filepath.open("r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f)

    if raw_data is None:
        return {}

    return _process_values(raw_data)


def get_settings() -> dict[str, Any]:
    """Load the main settings configuration.

    Returns:
        Parsed settings dictionary from config/settings.yaml.

    Raises:
        FileNotFoundError: If settings.yaml does not exist.
    """
    return load_yaml("settings.yaml")


def get_logging_config() -> dict[str, Any]:
    """Load the logging configuration.

    Returns:
        Parsed logging dictionary from config/logging.yaml.

    Raises:
        FileNotFoundError: If logging.yaml does not exist.
    """
    return load_yaml("logging.yaml")


def get_tools_config() -> dict[str, Any]:
    """Load the tools configuration.

    Returns:
        Parsed tools dictionary from config/tools.yaml.

    Raises:
        FileNotFoundError: If tools.yaml does not exist.
    """
    return load_yaml("tools.yaml")


def get_memory_config() -> dict[str, Any]:
    """Load the memory configuration.

    Returns:
        Parsed memory dictionary from config/memory.yaml.

    Raises:
        FileNotFoundError: If memory.yaml does not exist.
    """
    return load_yaml("memory.yaml")


def get_security_config() -> dict[str, Any]:
    """Load the security policy configuration.

    Returns:
        Parsed security dictionary from config/security.yaml.

    Raises:
        FileNotFoundError: If security.yaml does not exist.
    """
    return load_yaml("security.yaml")


def get_project_root() -> Path:
    """Return the absolute path to the project root directory.

    Returns:
        Path object pointing to the project root.
    """
    return _PROJECT_ROOT
