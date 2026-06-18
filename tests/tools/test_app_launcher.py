"""Tests for the app launcher tool."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from renine.tools.system.app_launcher import AppLauncherTool


@pytest.fixture
def mock_launcher_config():
    """Mock config for app launcher whitelist."""
    config = {
        "tools": {
            "app_launcher": {
                "whitelist": ["notepad", "calc"]
            }
        }
    }
    with patch("renine.tools.system.app_launcher.get_tools_config", return_value=config):
        yield config


def test_launch_whitelisted_app(mock_launcher_config) -> None:
    """Whitelisted application launches successfully."""
    tool = AppLauncherTool()
    with patch("renine.tools.system.app_launcher.subprocess.run") as mock_run:
        result = tool.execute(app_name="notepad")
        assert result.success is True
        assert result.data == {"app_name": "notepad", "status": "launched"}

        # Wait for thread to run mock_run if needed, or check if thread was started.
        # Since _run_app is run in a daemon thread, let's call it synchronously
        # or mock the threading.Thread start.
        # Let's verify our command list matches
        assert result.metadata is not None
        assert result.metadata["command"] == ["notepad.exe"]


def test_launch_blocked_app(mock_launcher_config) -> None:
    """Non-whitelisted application is blocked."""
    tool = AppLauncherTool()
    result = tool.execute(app_name="malicious_app")
    assert result.success is False
    assert "not in the allowed whitelist" in result.error
