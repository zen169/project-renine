import datetime
import os
import tempfile
from unittest.mock import patch

import pytest

from renine.databases.models import HistoryBase
from renine.databases.models.conversation import Conversation
from renine.databases.session import _engines, _sessionmakers, get_engine, get_session
from renine.memory import layer2_history


@pytest.fixture(autouse=True)
def setup_history_db():
    fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    _engines.clear()
    _sessionmakers.clear()

    mock_settings = {
        "databases": {
            "history_db": temp_db_path,
        },
    }
    with patch(
        "renine.databases.session.get_settings",
        return_value=mock_settings,
    ):
        engine = get_engine("history_db")
        HistoryBase.metadata.create_all(bind=engine)
        yield temp_db_path

    _engines.clear()
    _sessionmakers.clear()
    if os.path.exists(temp_db_path):
        try:
            os.remove(temp_db_path)
        except OSError:
            pass


def test_store_and_get_conversation():
    summary = "Discussion about the project setup"
    raw_turns = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
    ]
    date_val = datetime.date(2026, 6, 18)

    conv = layer2_history.store_conversation(
        summary=summary,
        raw_turns=raw_turns,
        date=date_val,
    )

    assert conv.id is not None
    assert conv.summary == summary
    assert conv.raw_turns == raw_turns
    assert conv.date == date_val

    retrieved = layer2_history.get_conversation(conv.id)
    assert retrieved is not None
    assert retrieved.summary == summary
    assert retrieved.raw_turns == raw_turns

    by_date = layer2_history.get_conversations_by_date(date_val)
    assert len(by_date) == 1
    assert by_date[0].id == conv.id


def test_get_recent_conversations():
    layer2_history.store_conversation("c1", [{"r": "u"}])
    layer2_history.store_conversation("c2", [{"r": "u"}])

    recent = layer2_history.get_recent_conversations(limit=1)
    assert len(recent) == 1
    assert recent[0].summary == "c2"


def test_delete_expired_conversations():
    conv = layer2_history.store_conversation("expired", [{"r": "u"}])

    db = get_session("history_db")
    db_conv = db.get(Conversation, conv.id)
    db_conv.created_at = datetime.datetime.now(
        datetime.timezone.utc,
    ) - datetime.timedelta(hours=50)
    db.commit()
    db.close()

    deleted = layer2_history.delete_expired_conversations(ttl_hours=48)
    assert deleted == 1
    assert layer2_history.get_conversation(conv.id) is None
