"""App launcher tool for Renine.

Allows opening system applications by name from a whitelisted set of tools.
Uses subprocess.run(shell=False) in a background thread to prevent blocking
the main execution pipeline.
"""
from __future__ import annotations

import subprocess
import threading
from typing import Any

from renine.core.config import get_tools_config
from renine.core.logging_config import get_logger
from renine.tools.permissions import PermissionLevel
from renine.tools.registry import BaseTool, ToolResult, register_tool

logger = get_logger(__name__)


def _run_app(cmd: list[str]) -> None:
    """Run the application command synchronously in a background thread.

    Args:
        cmd: List of command arguments.
    """
    try:
        logger.info("launching_app_process", cmd=cmd)
        subprocess.run(cmd, shell=False, check=True)
        logger.info("app_process_finished", cmd=cmd)
    except Exception as e:
        logger.error("app_process_failed", cmd=cmd, error=str(e))


@register_tool(
    name="app_launcher",
    description="Launch system applications by name",
    permission_level=PermissionLevel.ELEVATED,
    requires_confirmation=True,
)
class AppLauncherTool(BaseTool):
    """Tool to launch whitelisted applications by name."""

    def execute(self, app_name: str, **kwargs: Any) -> ToolResult:
        """Launch the requested application if it is whitelisted.

        Args:
            app_name: Name of the application (e.g., 'notepad', 'calc').
            **kwargs: Extra arguments.

        Returns:
            ToolResult indicating success or failure.
        """
        if not app_name:
            return ToolResult(success=False, error="Application name cannot be empty.")

        config = get_tools_config()
        launcher_config = config.get("tools", {}).get("app_launcher", {})
        whitelist = launcher_config.get("whitelist", [])

        normalized_app = app_name.lower().strip()
        normalized_whitelist = [w.lower().strip() for w in whitelist]

        if normalized_app not in normalized_whitelist:
            logger.warning("app_launch_blocked_not_whitelisted", app=app_name)
            return ToolResult(
                success=False,
                error=f"Application '{app_name}' is not in the allowed whitelist.",
            )

        # Build execution command (e.g., notepad -> notepad.exe)
        executable = normalized_app
        if not executable.endswith(".exe") and executable not in ["cmd", "explorer"]:
            executable = f"{executable}.exe"

        cmd = [executable]

        # Start process in a background thread to prevent blocking
        thread = threading.Thread(target=_run_app, args=(cmd,), daemon=True)
        thread.start()

        return ToolResult(
            success=True,
            data={"app_name": app_name, "status": "launched"},
            metadata={"command": cmd},
        )
