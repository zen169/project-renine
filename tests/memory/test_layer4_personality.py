import os
import tempfile
from unittest.mock import patch

import pytest

from renine.databases.models import PersonalityBase
from renine.databases.session import _engines, _sessionmakers, get_engine
from renine.memory import layer4_personality


@pytest.fixture(autouse=True)
def setup_personality_db():
    fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    _engines.clear()
    _sessionmakers.clear()

    mock_settings = {
        "databases": {
            "personality_db": temp_db_path,
        },
    }
    with patch(
        "renine.databases.session.get_settings",
        return_value=mock_settings,
    ), patch(
        "renine.memory.layer4_personality.add_to_vector_store",
    ) as mock_add, patch(
        "renine.memory.layer4_personality.delete_from_vector_store",
    ) as mock_del, patch(
        "renine.memory.layer4_personality.search_vector_store",
    ) as mock_search:
        engine = get_engine("personality_db")
        PersonalityBase.metadata.create_all(bind=engine)
        yield temp_db_path, mock_add, mock_del, mock_search

    _engines.clear()
    _sessionmakers.clear()
    if os.path.exists(temp_db_path):
        try:
            os.remove(temp_db_path)
        except OSError:
            pass


def test_store_and_get_person(setup_personality_db):
    _, mock_add, _, _ = setup_personality_db

    name = "John Doe"
    relationship = "Brother"
    notes = "Loves chocolate chip cookies"
    hobbies = ["Guitar", "Gaming"]
    food_preferences = ["Pizza"]

    person = layer4_personality.store_person(
        name=name,
        relationship=relationship,
        age=30,
        birthday="1996-01-01",
        food_preferences=food_preferences,
        hobbies=hobbies,
        notes=notes,
    )

    assert person.id is not None
    assert person.name == name
    assert person.relationship == relationship
    assert person.age == 30
    assert person.hobbies == hobbies

    mock_add.assert_called_once()

    retrieved = layer4_personality.get_person(name)
    assert retrieved is not None
    assert retrieved.notes == notes


def test_delete_person(setup_personality_db):
    _, _, mock_del, _ = setup_personality_db

    name = "Jane Doe"
    layer4_personality.store_person(name, "Sister", notes="Hates cheese")

    deleted = layer4_personality.delete_person(name)
    assert deleted is True

    mock_del.assert_called_once_with("personality", "person:Jane Doe")
    assert layer4_personality.get_person(name) is None


def test_list_people(setup_personality_db):
    layer4_personality.store_person("Alice", "Friend")
    layer4_personality.store_person("Bob", "Co-worker")

    people = layer4_personality.list_people()
    assert len(people) == 2
    assert {p.name for p in people} == {"Alice", "Bob"}


def test_search_people(setup_personality_db):
    _, _, _, mock_search = setup_personality_db
    layer4_personality.store_person(
        "Charlie", "Chef", notes="Likes baking bread",
    )

    mock_search.return_value = [
        {
            "id": "person:Charlie",
            "document": (
                "Name: Charlie. Relationship: Chef. Hobbies: None. "
                "Food Preferences: None. Notes: Likes baking bread"
            ),
            "metadata": {"name": "Charlie"},
            "distance": 0.1,
        },
    ]

    results = layer4_personality.search_people("baking bread")
    assert len(results) == 1
    assert results[0]["name"] == "Charlie"
    assert results[0]["notes"] == "Likes baking bread"
    assert results[0]["distance"] == 0.1
