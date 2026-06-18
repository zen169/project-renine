"""Tests for the SpreadsheetAgent."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from renine.agents.spreadsheet_agent import SpreadsheetAgent


@pytest.fixture
def agent():
    """Fixture to instantiate SpreadsheetAgent."""
    return SpreadsheetAgent()


@pytest.fixture(autouse=True)
def mock_security_config(tmp_path: Path):
    """Auto-patch security settings for spreadsheet testing."""
    config = {
        "security": {
            "filesystem": {
                "allowed_paths": [str(tmp_path)],
                "blocked_paths": [],
                "max_read_size_bytes": 1000000,
            }
        }
    }
    with patch("renine.security.input_validator.get_security_config", return_value=config):
        yield config


@pytest.fixture
def temp_csv_file(tmp_path: Path):
    """Create a temporary CSV file with test data."""
    df = pd.DataFrame({
        "Name": ["Alice", "Bob", "Charlie"],
        "Age": [25, 30, 35],
        "Salary": [50000, 60000, 70000]
    })
    csv_path = tmp_path / "employees.csv"
    df.to_csv(csv_path, index=False)
    yield csv_path


def test_no_file_path_in_query(agent) -> None:
    """Agent returns a prompt to specify path if missing."""
    res = agent.process("show me the summary")
    assert res["success"] is False
    assert "specify a spreadsheet file path" in res["content"]


def test_file_not_found(agent, tmp_path) -> None:
    """Agent returns error if file path does not exist."""
    res = agent.process(f"summarize {tmp_path}/nonexistent.csv")
    assert res["success"] is False
    assert "File not found" in res["content"]


def test_columns_query(agent, temp_csv_file) -> None:
    """Agent returns column names list from CSV."""
    res = agent.process(f"list the columns in {temp_csv_file}")
    assert res["success"] is True
    assert "Columns: Name, Age, Salary" in res["content"]
    assert res["shape"] == (3, 3)


def test_summary_query(agent, temp_csv_file) -> None:
    """Agent returns data stats description from CSV."""
    res = agent.process(f"summarize data in {temp_csv_file}")
    assert res["success"] is True
    assert "Age" in res["content"]
    assert "Salary" in res["content"]


@patch("renine.agents.spreadsheet_agent.check_connection", return_value=True)
@patch("renine.agents.spreadsheet_agent.chat", return_value="The average salary is 60,000.")
def test_natural_language_query_online(mock_chat, mock_check, agent, temp_csv_file) -> None:
    """Agent queries LLM for general questions about spreadsheet data when online."""
    res = agent.process(f"what is the average salary in {temp_csv_file}?")
    assert res["success"] is True
    assert "average salary is 60,000" in res["content"]
    mock_chat.assert_called_once()
