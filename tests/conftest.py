"""Shared test fixtures for the Renine test suite."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def tmp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory with test YAML files.

    Args:
        tmp_path: Pytest-provided temporary directory.

    Returns:
        Path to the temporary config directory.
    """
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def tmp_data_dir(tmp_path: Path) -> Path:
    """Create a temporary data directory for test databases.

    Args:
        tmp_path: Pytest-provided temporary directory.

    Returns:
        Path to the temporary data directory.
    """
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def tmp_logs_dir(tmp_path: Path) -> Path:
    """Create a temporary logs directory.

    Args:
        tmp_path: Pytest-provided temporary directory.

    Returns:
        Path to the temporary logs directory.
    """
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    return logs_dir
