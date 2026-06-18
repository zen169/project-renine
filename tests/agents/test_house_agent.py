"""Tests for the HouseAgent."""
from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

import pytest

from renine.agents.base_agent import MemoryAccessLevel
from renine.agents.house_agent import HouseAgent
from renine.databases.models import MindBase
from renine.databases.session import _engines, _sessionmakers, get_engine


@pytest.fixture(autouse=True)
def setup_mind_db():
    """Create a temporary sqlite database for testing."""
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
    ):
        engine = get_engine("mind_db")
        MindBase.metadata.create_all(bind=engine)
        yield temp_db_path

    _engines.clear()
    _sessionmakers.clear()
    if os.path.exists(temp_db_path):
        try:
            os.remove(temp_db_path)
        except OSError:
            pass


def test_house_agent_manifest() -> None:
    """Test the agent manifest declarations."""
    agent = HouseAgent()
    manifest = agent.get_manifest()
    assert manifest.name == "house"
    assert manifest.memory_access_level == MemoryAccessLevel.FULL_ACCESS


def test_house_agent_crud() -> None:
    """Test CRUD operations on household items."""
    agent = HouseAgent()

    # Create
    item = agent.add_item(
        name="Kitchen Fridge",
        item_type="appliance",
        room="Kitchen",
        status="functional",
        details={"brand": "Samsung", "color": "Silver"},
    )
    assert item.id is not None
    assert item.name == "Kitchen Fridge"
    assert item.room == "Kitchen"

    # Retrieve
    retrieved = agent.get_item("Kitchen Fridge")
    assert retrieved is not None
    assert retrieved.item_type == "appliance"

    # Update
    updated = agent.update_item("Kitchen Fridge", status="maintenance")
    assert updated is not None
    assert updated.status == "maintenance"

    # List
    items = agent.list_items()
    assert len(items) == 1
    assert items[0].name == "Kitchen Fridge"

    # Delete
    deleted = agent.delete_item("Kitchen Fridge")
    assert deleted is True
    assert agent.get_item("Kitchen Fridge") is None


def test_house_queries() -> None:
    """Test querying rooms for specific item types."""
    agent = HouseAgent()

    # Populate household items
    agent.add_item("Fridge", "appliance", "Kitchen")
    agent.add_item("Oven", "appliance", "Kitchen")
    agent.add_item("Dining Table", "furniture", "Kitchen")
    agent.add_item("TV", "appliance", "Living Room")

    # Query: what appliances are in the kitchen?
    res = agent.process("what appliances are in the Kitchen?")
    assert res["success"] is True
    assert len(res["items"]) == 2
    names = {i["name"] for i in res["items"]}
    assert names == {"Fridge", "Oven"}

    # Query: what items are in the kitchen?
    res_all = agent.process("what items are in the kitchen?")
    assert res_all["success"] is True
    assert len(res_all["items"]) == 3
    types = {i["type"] for i in res_all["items"]}
    assert types == {"appliance", "furniture"}
