"""Tests for renine.agents.browser_agent — Browser Agent.

Validates:
- Planning translates user input into URL and actions (with mock LLM).
- Tool execution is called via execute_tool with correct permissions.
- Result text is summarized and contains the untrusted content disclaimer.
- Handles tool failures gracefully.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from renine.agents.browser_agent import BrowserAgent
from renine.tools.registry import ToolResult


class TestBrowserAgent:
    """Tests for the BrowserAgent implementation."""

    @patch("renine.agents.browser_agent.execute_tool")
    @patch("renine.agents.browser_agent.ollama_client")
    def test_browser_agent_process_flow(
        self, mock_ollama: MagicMock, mock_execute_tool: MagicMock
    ) -> None:
        """BrowserAgent plans actions, executes tool, and summarizes content with safety warnings."""
        # 1. Setup Ollama mock for planning and summarization
        mock_ollama.check_connection.return_value = True
        
        plan_json = json.dumps({
            "url": "https://example.com/search",
            "actions": [{"type": "fill", "selector": "#query", "text": "shoes"}]
        })
        
        # Side effect for chat calls: first planning, second summarizing
        mock_ollama.chat.side_effect = [
            plan_json,
            "Summary of shoe products found."
        ]

        # 2. Setup Tool execution mock
        mock_execute_tool.return_value = ToolResult(
            success=True,
            data={
                "title": "Shoe Store",
                "url": "https://example.com/search?q=shoes",
                "text": "Extracted shoe deals: Running shoes $50...",
                "untrusted": True,
            }
        )

        agent = BrowserAgent()
        result = agent.process("search shoes on example.com")

        # 3. Assertions
        assert result["success"] is True
        assert result["source_agent"] == "browser"
        assert "Summary of shoe products found." in result["content"]
        assert "[UNTRUSTED CONTENT REVIEW REQUIRED]" in result["content"]
        assert result["extracted_metadata"]["untrusted"] is True
        
        # Verify tool execution parameters
        mock_execute_tool.assert_called_once_with(
            "browser",
            caller_permission=agent.get_manifest().permission_level,
            caller_agent="browser",
            url="https://example.com/search",
            actions=[{"type": "fill", "selector": "#query", "text": "shoes"}],
        )

    @patch("renine.agents.browser_agent.execute_tool")
    @patch("renine.agents.browser_agent.ollama_client")
    def test_browser_agent_handles_tool_failure(
        self, mock_ollama: MagicMock, mock_execute_tool: MagicMock
    ) -> None:
        """BrowserAgent handles browser tool errors gracefully."""
        mock_ollama.check_connection.return_value = False  # Ollama offline fallback planning
        
        mock_execute_tool.return_value = ToolResult(
            success=False,
            error="Playwright context crashed",
        )

        agent = BrowserAgent()
        result = agent.process("go to google.com")

        assert result["success"] is False
        assert "Failed to automate browser: Playwright context crashed" in result["content"]

    def test_browser_agent_cannot_access_layer3_memory(self) -> None:
        """BrowserAgent cannot write to or access Layer 3 memory."""
        agent = BrowserAgent()

        assert agent.validate_memory_access(3) is False

    def test_browser_agent_cannot_access_layer4_memory(self) -> None:
        """BrowserAgent cannot write to or access Layer 4 memory."""
        agent = BrowserAgent()

        assert agent.validate_memory_access(4) is False

    @patch("renine.memory.layer4_personality.store_person")
    @patch("renine.memory.layer3_mind.store_fact")
    @patch("renine.agents.browser_agent.execute_tool")
    @patch("renine.agents.browser_agent.ollama_client")
    def test_browser_agent_does_not_write_untrusted_content_to_memory(
        self,
        mock_ollama: MagicMock,
        mock_execute_tool: MagicMock,
        mock_store_fact: MagicMock,
        mock_store_person: MagicMock,
    ) -> None:
        """Untrusted browser content is returned to the user, not stored in Layer 3 or 4."""
        mock_ollama.check_connection.return_value = False
        mock_execute_tool.return_value = ToolResult(
            success=True,
            data={
                "title": "External Page",
                "url": "https://example.com",
                "text": "External untrusted text",
                "untrusted": True,
            },
        )

        agent = BrowserAgent()
        result = agent.process("go to https://example.com")

        assert result["success"] is True
        assert result["extracted_metadata"]["untrusted"] is True
        mock_store_fact.assert_not_called()
        mock_store_person.assert_not_called()
