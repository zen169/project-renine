"""Web browser tool for Renine.

Uses Playwright headless browser automation to navigate pages, interact
with elements (click, type), and extract text content securely.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright

from renine.core.logging_config import get_logger
from renine.tools.permissions import PermissionLevel
from renine.tools.registry import BaseTool, ToolResult, register_tool

logger = get_logger(__name__)


@register_tool(
    name="browser",
    description="Automate headless browser operations: navigate, click, fill forms, and extract text.",
    permission_level=PermissionLevel.ELEVATED,
    requires_confirmation=True,
)
class BrowserTool(BaseTool):
    """Tool to control a headless web browser for research, shopping, and form completion."""

    def _cleanup_profile_dir(self, temp_dir: str) -> str | None:
        """Remove the isolated browser profile directory and verify deletion.

        Args:
            temp_dir: Temporary profile directory path.

        Returns:
            Error text if cleanup failed, otherwise None.
        """
        path = Path(temp_dir)
        if not path.name.startswith("renine_playwright_"):
            return f"Refusing to clean unexpected browser profile path: {temp_dir}"

        try:
            shutil.rmtree(path, ignore_errors=False)
        except Exception as e:
            return str(e)

        if path.exists():
            return f"Browser profile directory still exists after cleanup: {temp_dir}"
        return None

    def execute(
        self,
        url: str | None = None,
        actions: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        """Execute browser operations.

        Args:
            url: Optional URL to navigate to first.
            actions: Optional list of actions to run on the page. Each action
                is a dict with 'type' ('click', 'fill', 'wait') and key-specific params
                (e.g., 'selector', 'text', 'timeout').
            **kwargs: Extra arguments.

        Returns:
            ToolResult containing extracted page text and status.
        """
        if not url and not actions:
            return ToolResult(
                success=False,
                error="Must provide either a URL to navigate to or actions to perform.",
            )

        temp_dir = tempfile.mkdtemp(prefix="renine_playwright_")
        logger.info("browser_tool_starting", temp_dir=temp_dir, url=url)
        result: ToolResult | None = None

        try:
            with sync_playwright() as p:
                # Setup isolated browser context with required settings
                context = p.chromium.launch_persistent_context(
                    user_data_dir=temp_dir,
                    headless=True,
                    no_viewport=False,  # Essential requirement
                )
                
                try:
                    page = context.new_page()
                    
                    # 1. Navigation
                    if url:
                        logger.info("browser_tool_navigating", url=url)
                        page.goto(url, wait_until="load", timeout=30000)

                    # 2. Sequential Actions
                    if actions:
                        for idx, action in enumerate(actions):
                            action_type = action.get("type")
                            selector = action.get("selector")
                            
                            logger.info(
                                "browser_tool_action",
                                index=idx,
                                type=action_type,
                                selector=selector,
                            )

                            if action_type == "click":
                                if not selector:
                                    raise ValueError(f"Action {idx}: 'selector' is required for click.")
                                page.wait_for_selector(selector, timeout=10000)
                                page.click(selector)

                            elif action_type == "fill":
                                if not selector:
                                    raise ValueError(f"Action {idx}: 'selector' is required for fill.")
                                text = action.get("text", "")
                                page.wait_for_selector(selector, timeout=10000)
                                page.fill(selector, text)

                            elif action_type == "wait":
                                timeout = action.get("timeout", 5000)
                                if selector:
                                    page.wait_for_selector(selector, timeout=timeout)
                                else:
                                    page.wait_for_timeout(timeout)

                            else:
                                raise ValueError(f"Unknown action type: {action_type}")

                    # 3. Text Extraction
                    title = page.title()
                    current_url = page.url
                    # Extract page body text content
                    text_content = page.locator("body").inner_text()

                    data = {
                        "title": title,
                        "url": current_url,
                        "text": text_content,
                        "untrusted": True,  # Security boundary classification
                    }

                    logger.info("browser_tool_success", url=current_url, title=title)
                    result = ToolResult(success=True, data=data)

                finally:
                    try:
                        context.clear_cookies()
                    except Exception as e:
                        logger.warning("browser_tool_clear_cookies_failed", error=str(e))
                    context.close()

        except Exception as e:
            logger.exception("browser_tool_failed")
            result = ToolResult(success=False, error=str(e))

        finally:
            cleanup_error = self._cleanup_profile_dir(temp_dir)
            if cleanup_error:
                logger.error(
                    "browser_tool_cleanup_failed",
                    temp_dir=temp_dir,
                    error=cleanup_error,
                )
                if result and result.success:
                    result = ToolResult(
                        success=False,
                        error=f"Browser profile cleanup failed: {cleanup_error}",
                        metadata={"cleanup_failed": True},
                    )
                elif result:
                    result.metadata["cleanup_failed"] = True
                    result.metadata["cleanup_error"] = cleanup_error
            else:
                logger.info("browser_tool_cleanup_complete", temp_dir=temp_dir)

        return result or ToolResult(success=False, error="Browser execution did not complete.")
