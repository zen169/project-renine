"""Tests for the CodingAgent."""
from __future__ import annotations

from unittest.mock import patch

import pytest

from renine.agents.coding_agent import CodingAgent
from renine.tools.registry import ToolResult


@pytest.fixture
def agent():
    """Fixture to instantiate CodingAgent."""
    return CodingAgent()


@patch("renine.agents.coding_agent.check_connection", return_value=True)
@patch("renine.agents.coding_agent.chat", return_value="Here is the explanation for your code.")
def test_coding_query_online(mock_chat, mock_check, agent) -> None:
    """Coding agent calls Ollama successfully when online."""
    result = agent.process("explain function def foo(): pass")
    assert result["success"] is True
    assert "explanation for your code" in result["content"]
    assert result["source_agent"] == "coding"


@patch("renine.agents.coding_agent.check_connection", return_value=False)
def test_coding_query_offline(mock_check, agent) -> None:
    """Coding agent returns offline message when Ollama is unreachable."""
    result = agent.process("explain code")
    assert result["success"] is False
    assert "offline" in result["content"].lower()


@patch("renine.agents.coding_agent.check_connection", return_value=True)
@patch("renine.agents.coding_agent.chat")
@patch("renine.agents.coding_agent.execute_tool")
def test_coding_query_with_file_read(mock_execute, mock_chat, mock_check, agent) -> None:
    """Coding agent reads the file using file_reader tool and includes it in the prompt."""
    mock_execute.return_value = ToolResult(
        success=True,
        data={"text": "def add(a, b): return a + b"}
    )
    mock_chat.return_value = "This adds two numbers."

    result = agent.process("explain the code in c:/workspace/math.py")

    assert result["success"] is True
    assert result["file_read"] == "c:/workspace/math.py"
    mock_execute.assert_called_once()
    # Ensure file content was passed to LLM
    args, kwargs = mock_chat.call_args
    prompt = kwargs.get("messages", args[0] if args else [])[0]["content"]
    assert "def add(a, b)" in prompt
