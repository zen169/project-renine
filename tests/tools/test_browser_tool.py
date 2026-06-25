"""Tests for renine.tools.web.browser_tool — Playwright browser automation.

Validates:
- Successful navigation, sequential page interactions (click/fill), and text extraction.
- Enforces isolated temp directories and no viewport configuration.
- Extracted content is marked as untrusted.
- Error handling on browser execution failures.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from renine.tools.web.browser_tool import BrowserTool


class TestBrowserTool:
    """Tests for the BrowserTool implementation."""

    @patch("renine.tools.web.browser_tool.sync_playwright")
    def test_browser_tool_navigation_and_extraction(self, mock_sync_playwright: MagicMock) -> None:
        """Browser tool successfully navigates, interacts, extracts content, and sets security flags."""
        # 1. Setup mocks
        mock_playwright = MagicMock()
        mock_sync_playwright.return_value.__enter__.return_value = mock_playwright
        
        mock_context = MagicMock()
        mock_page = MagicMock()
        
        mock_playwright.chromium.launch_persistent_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        
        # Page properties & methods
        mock_page.title.return_value = "Example Page"
        mock_page.url = "https://example.com/page"
        mock_page.locator.return_value.inner_text.return_value = "This is the text on the page."

        # 2. Run the tool
        tool = BrowserTool()
        url = "https://example.com"
        actions = [
            {"type": "fill", "selector": "#input", "text": "test query"},
            {"type": "click", "selector": "#submit"},
            {"type": "wait", "timeout": 1000},
        ]
        
        result = tool.execute(url=url, actions=actions)

        # 3. Assertions
        assert result.success is True
        assert result.data["title"] == "Example Page"
        assert result.data["url"] == "https://example.com/page"
        assert result.data["text"] == "This is the text on the page."
        assert result.data["untrusted"] is True  # Enforces UNTRUSTED classification
        
        # Verify Playwright was called with isolation and no_viewport config
        mock_playwright.chromium.launch_persistent_context.assert_called_once()
        kwargs = mock_playwright.chromium.launch_persistent_context.call_args[1]
        assert kwargs["no_viewport"] is False
        assert "renine_playwright_" in kwargs["user_data_dir"]

        # Verify page calls
        mock_page.goto.assert_called_with(url, wait_until="load", timeout=30000)
        mock_page.fill.assert_called_with("#input", "test query")
        mock_page.click.assert_called_with("#submit")
        mock_context.clear_cookies.assert_called_once()
        mock_context.storage_state.assert_not_called()
        mock_context.close.assert_called_once()

    @patch("renine.tools.web.browser_tool.sync_playwright")
    def test_browser_tool_handles_exceptions(self, mock_sync_playwright: MagicMock) -> None:
        """Browser tool handles exceptions gracefully and returns ToolResult with success=False."""
        mock_sync_playwright.side_effect = Exception("Failed to launch chromium")

        tool = BrowserTool()
        result = tool.execute(url="https://example.com")

        assert result.success is False
        assert "Failed to launch chromium" in result.error

    def test_cleanup_profile_dir_removes_temp_profile(self) -> None:
        """Profile cleanup removes isolated temporary browser directories."""
        tool = BrowserTool()
        profile_dir = "C:\\Temp\\renine_playwright_test_profile"

        with (
            patch("renine.tools.web.browser_tool.shutil.rmtree") as mock_rmtree,
            patch("renine.tools.web.browser_tool.Path.exists", return_value=False),
        ):
            cleanup_error = tool._cleanup_profile_dir(profile_dir)

        assert cleanup_error is None
        mock_rmtree.assert_called_once_with(Path(profile_dir), ignore_errors=False)

    def test_cleanup_profile_dir_refuses_unexpected_path(self) -> None:
        """Cleanup refuses paths that do not look like Renine browser profiles."""
        tool = BrowserTool()
        cleanup_error = tool._cleanup_profile_dir("C:\\Temp\\not_a_browser_profile")

        assert cleanup_error is not None
        assert "Refusing to clean unexpected browser profile path" in cleanup_error

    @patch("renine.tools.web.browser_tool.BrowserTool._cleanup_profile_dir")
    @patch("renine.tools.web.browser_tool.sync_playwright")
    def test_browser_tool_reports_cleanup_failure(
        self,
        mock_sync_playwright: MagicMock,
        mock_cleanup: MagicMock,
    ) -> None:
        """A successful browser run is not reported clean if profile cleanup fails."""
        mock_cleanup.return_value = "profile locked"
        mock_playwright = MagicMock()
        mock_sync_playwright.return_value.__enter__.return_value = mock_playwright
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_playwright.chromium.launch_persistent_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_page.title.return_value = "Example Page"
        mock_page.url = "https://example.com/page"
        mock_page.locator.return_value.inner_text.return_value = "Text"

        tool = BrowserTool()
        result = tool.execute(url="https://example.com")

        assert result.success is False
        assert "Browser profile cleanup failed" in result.error
        assert result.metadata["cleanup_failed"] is True

    @patch("renine.tools.web.browser_tool.sync_playwright")
    def test_browser_tool_does_not_export_storage_state(
        self,
        mock_sync_playwright: MagicMock,
    ) -> None:
        """Browser storage export APIs are not used, preventing persisted state leaks."""
        mock_playwright = MagicMock()
        mock_sync_playwright.return_value.__enter__.return_value = mock_playwright
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_playwright.chromium.launch_persistent_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_page.title.return_value = "Example Page"
        mock_page.url = "https://example.com/page"
        mock_page.locator.return_value.inner_text.return_value = "Text"

        tool = BrowserTool()
        result = tool.execute(url="https://example.com")

        assert result.success is True
        mock_context.storage_state.assert_not_called()
        mock_context.clear_cookies.assert_called_once()
