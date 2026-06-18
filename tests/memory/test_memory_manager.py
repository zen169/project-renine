from unittest.mock import MagicMock, patch

import pytest

from renine.memory.memory_manager import MemoryManager


@pytest.fixture
def mock_layers():
    with patch(
        "renine.memory.memory_manager.layer2_history",
    ) as mock_l2, patch(
        "renine.memory.memory_manager.layer3_mind",
    ) as mock_l3, patch(
        "renine.memory.memory_manager.layer4_personality",
    ) as mock_l4, patch(
        "renine.memory.memory_manager.ConversationContext",
    ) as mock_ctx_class:
        mock_ctx = MagicMock()
        mock_ctx_class.return_value = mock_ctx
        yield mock_ctx, mock_l2, mock_l3, mock_l4


def test_memory_manager_context_delegation(mock_layers):
    mock_ctx, _, _, _ = mock_layers

    manager = MemoryManager()

    manager.add_message("user", "hello")
    mock_ctx.add_message.assert_called_once_with(
        "user", "hello", metadata=None,
    )

    mock_ctx.get_messages.return_value = [{"role": "user", "content": "hello"}]
    assert manager.get_messages() == [{"role": "user", "content": "hello"}]

    manager.clear_context()
    mock_ctx.clear.assert_called_once()


def test_memory_manager_persist_session(mock_layers):
    mock_ctx, mock_l2, _, _ = mock_layers
    mock_ctx.get_messages.return_value = [{"role": "user", "content": "hello"}]

    manager = MemoryManager()
    manager.persist_current_session("session summary")

    mock_l2.store_conversation.assert_called_once_with(
        summary="session summary",
        raw_turns=[{"role": "user", "content": "hello"}],
    )
    mock_ctx.clear.assert_called_once()


def test_memory_manager_mind_delegation(mock_layers):
    _, _, mock_l3, _ = mock_layers

    manager = MemoryManager()

    manager.store_fact("tasks", "task1", {"desc": "code"}, "coding task")
    mock_l3.store_fact.assert_called_once_with(
        "tasks", "task1", {"desc": "code"}, "coding task",
    )

    mock_record = MagicMock()
    mock_record.key = "task1"
    mock_record.value = {"desc": "code"}
    mock_record.summary = "coding task"
    mock_record.updated_at.isoformat.return_value = "2026-06-18T12:00:00"
    mock_l3.get_fact.return_value = mock_record

    res = manager.get_fact("tasks", "task1")
    assert res == {
        "key": "task1",
        "value": {"desc": "code"},
        "summary": "coding task",
        "updated_at": "2026-06-18T12:00:00",
    }


def test_memory_manager_personality_delegation(mock_layers):
    _, _, _, mock_l4 = mock_layers

    manager = MemoryManager()

    manager.store_person("Alice", "Friend", age=25)
    mock_l4.store_person.assert_called_once_with(
        name="Alice",
        relationship="Friend",
        age=25,
        birthday=None,
        food_preferences=None,
        hobbies=None,
        personality_traits=None,
        goals=None,
        habits=None,
        notes="",
    )

    mock_l4.delete_person.return_value = True
    assert manager.delete_person("Alice") is True
