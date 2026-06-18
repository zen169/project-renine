from unittest.mock import MagicMock

import pytest

from renine.agents.base_agent import MemoryAccessLevel
from renine.agents.memory_agent import MemoryAgent


@pytest.fixture
def mock_memory_manager():
    manager = MagicMock()
    return manager


def test_memory_agent_manifest():
    agent = MemoryAgent()
    manifest = agent.get_manifest()
    assert manifest.name == "memory"
    assert manifest.memory_access_level == MemoryAccessLevel.FULL_ACCESS


def test_memory_agent_process(mock_memory_manager):
    mock_memory_manager.get_recent_conversations.return_value = [
        {"date": "2026-06-18", "summary": "Setup discussion"},
    ]
    mock_memory_manager.search_facts.return_value = [
        {"summary": "Framework laptop has 64GB RAM", "distance": 0.1},
    ]
    mock_memory_manager.search_people.return_value = [
        {
            "name": "Alice",
            "relationship": "Friend",
            "notes": "Loves cookies",
            "distance": 0.1,
        },
    ]

    agent = MemoryAgent(memory_manager=mock_memory_manager)
    res = agent.process("Tell me about Alice and my laptop")

    assert res["success"] is True
    content = res["content"]
    assert "Setup discussion" in content
    assert "Framework laptop has 64GB RAM" in content
    assert "Alice" in content
