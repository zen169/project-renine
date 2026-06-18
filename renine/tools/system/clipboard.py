"""Clipboard tool for Renine.

Provides read and write access to the system clipboard using Windows ctypes API
for high performance and zero external dependencies.
"""
from __future__ import annotations

import ctypes
from typing import Any

from renine.core.logging_config import get_logger
from renine.tools.permissions import PermissionLevel
from renine.tools.registry import BaseTool, ToolResult, register_tool

logger = get_logger(__name__)

# Windows API constants
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 2


def _get_clipboard_data() -> str:
    """Retrieve text from the Windows clipboard using ctypes.

    Returns:
        The text content of the clipboard, or an empty string.
    """
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    if not user32.OpenClipboard(None):
        logger.warning("failed_to_open_clipboard")
        return ""

    try:
        if not user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
            return ""

        handle = user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""

        data_ptr = kernel32.GlobalLock(handle)
        if not data_ptr:
            return ""

        try:
            text: str = ctypes.c_wchar_p(data_ptr).value or ""
            return text
        finally:
            kernel32.GlobalUnlock(handle)
    finally:
        user32.CloseClipboard()


def _set_clipboard_data(text: str) -> bool:
    """Write text to the Windows clipboard using ctypes.

    Args:
        text: The text to write.

    Returns:
        True if successful, False otherwise.
    """
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    if not user32.OpenClipboard(None):
        logger.warning("failed_to_open_clipboard")
        return False

    try:
        user32.EmptyClipboard()
        char_count = len(text) + 1
        size = char_count * ctypes.sizeof(ctypes.c_wchar)

        handle = kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
        if not handle:
            return False

        data_ptr = kernel32.GlobalLock(handle)
        if not data_ptr:
            return False

        try:
            ctypes.memmove(data_ptr, text, size)
        finally:
            kernel32.GlobalUnlock(handle)

        user32.SetClipboardData(CF_UNICODETEXT, handle)
        return True
    finally:
        user32.CloseClipboard()


@register_tool(
    name="clipboard",
    description="Read from or write to the system clipboard",
    permission_level=PermissionLevel.STANDARD,
    requires_confirmation=False,
)
class ClipboardTool(BaseTool):
    """Tool to read or write clipboard content."""

    def execute(self, action: str, text: str | None = None, **kwargs: Any) -> ToolResult:
        """Execute the clipboard action.

        Args:
            action: Action to perform ('read' or 'write').
            text: Text to write, required if action is 'write'.
            **kwargs: Extra arguments.

        Returns:
            ToolResult indicating success or failure.
        """
        action = action.lower().strip()

        if action == "read":
            content = _get_clipboard_data()
            return ToolResult(success=True, data={"text": content})

        if action == "write":
            if text is None:
                return ToolResult(
                    success=False,
                    error="Argument 'text' is required when action is 'write'.",
                )
            success = _set_clipboard_data(text)
            if success:
                return ToolResult(success=True, data={"status": "copied"})
            return ToolResult(success=False, error="Failed to write to clipboard.")

        return ToolResult(
            success=False,
            error=f"Unknown clipboard action: '{action}'. Supported: read, write",
        )
