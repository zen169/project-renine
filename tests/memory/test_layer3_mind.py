import os
import tempfile
from unittest.mock import patch

import pytest

from renine.databases.models import MindBase
from renine.databases.session import _engines, _sessionmakers, get_engine
from renine.memory import layer3_mind


@pytest.fixture(autouse=True)
def setup_mind_db():
    fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    _engines.clear()
    _sessionmakers.clear()

    mock_settings = {
        "databases": {
            "mind_db": temp_db_path,
        },
    }
    with patch(
        "renine.databases.session.get_settings",
        return_value=mock_settings,
    ), patch(
        "renine.memory.layer3_mind.add_to_vector_store",
    ) as mock_add, patch(
        "renine.memory.layer3_mind.delete_from_vector_store",
    ) as mock_del, patch(
        "renine.memory.layer3_mind.search_vector_store",
    ) as mock_search:
        engine = get_engine("mind_db")
        MindBase.metadata.create_all(bind=engine)
        yield temp_db_path, mock_add, mock_del, mock_search

    _engines.clear()
    _sessionmakers.clear()
    if os.path.exists(temp_db_path):
        try:
            os.remove(temp_db_path)
        except OSError:
            pass


def test_store_and_get_fact(setup_mind_db):
    _, mock_add, _, _ = setup_mind_db

    namespace = "inventory"
    key = "laptop"
    value = {"brand": "Framework", "ram": "64GB"}
    summary = "Framework Laptop 16-inch with 64GB RAM"

    record = layer3_mind.store_fact(
        namespace=namespace,
        key=key,
        value=value,
        summary=summary,
    )

    assert record.id is not None
    assert record.namespace == namespace
    assert record.key == key
    assert record.value == value
    assert record.summary == summary

    mock_add.assert_called_once_with(
        collection_name="mind_inventory",
        id_="inventory:laptop",
        text=summary,
        metadata={"namespace": namespace, "key": key},
    )

    retrieved = layer3_mind.get_fact(namespace, key)
    assert retrieved is not None
    assert retrieved.value == value


def test_delete_fact(setup_mind_db):
    _, _, mock_del, _ = setup_mind_db

    namespace = "pets"
    key = "dog"
    layer3_mind.store_fact(namespace, key, {"name": "Buddy"}, "My dog Buddy")

    deleted = layer3_mind.delete_fact(namespace, key)
    assert deleted is True

    mock_del.assert_called_once_with("mind_pets", "pets:dog")
    assert layer3_mind.get_fact(namespace, key) is None


def test_list_facts(setup_mind_db):
    namespace = "tasks"
    layer3_mind.store_fact(
        namespace, "t1", {"desc": "write tests"}, "Write tests",
    )
    layer3_mind.store_fact(
        namespace, "t2", {"desc": "run tests"}, "Run tests",
    )

    facts = layer3_mind.list_facts(namespace)
    assert len(facts) == 2
    assert {f.key for f in facts} == {"t1", "t2"}


def test_search_facts(setup_mind_db):
    _, _, _, mock_search = setup_mind_db
    namespace = "notes"
    layer3_mind.store_fact(
        namespace,
        "n1",
        {"content": "important note"},
        "Important note about tests",
    )

    mock_search.return_value = [
        {
            "id": "notes:n1",
            "document": "Important note about tests",
            "metadata": {"namespace": namespace, "key": "n1"},
            "distance": 0.2,
        },
    ]

    results = layer3_mind.search_facts(namespace, "tests")
    assert len(results) == 1
    assert results[0]["key"] == "n1"
    assert results[0]["value"] == {"content": "important note"}
    assert results[0]["distance"] == 0.2
