"""Tests for the InventoryAgent."""
from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

import pytest

from renine.agents.base_agent import MemoryAccessLevel
from renine.agents.inventory_agent import InventoryAgent
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


def test_inventory_agent_manifest() -> None:
    """Test the agent manifest declarations."""
    agent = InventoryAgent()
    manifest = agent.get_manifest()
    assert manifest.name == "inventory"
    assert manifest.memory_access_level == MemoryAccessLevel.FULL_ACCESS


def test_inventory_agent_crud() -> None:
    """Test CRUD operations on the inventory database."""
    agent = InventoryAgent()

    # Create
    item = agent.add_item(
        name="pasta",
        category="ingredient",
        quantity=500.0,
        unit="g",
        threshold=100.0,
        location="pantry",
    )
    assert item.id is not None
    assert item.name == "pasta"
    assert item.quantity == 500.0

    # Retrieve
    retrieved = agent.get_item("pasta")
    assert retrieved is not None
    assert retrieved.quantity == 500.0

    # Update
    updated = agent.update_item("pasta", quantity=400.0, location="fridge")
    assert updated is not None
    assert updated.quantity == 400.0
    assert updated.location == "fridge"

    # List
    items = agent.list_items()
    assert len(items) == 1
    assert items[0].name == "pasta"

    # Delete
    deleted = agent.delete_item("pasta")
    assert deleted is True
    assert agent.get_item("pasta") is None


def test_what_can_we_cook() -> None:
    """Test recipe checks with different inventory states."""
    agent = InventoryAgent()

    # 1. Empty inventory -> cannot cook anything
    cookable, status = agent.what_can_we_cook()
    assert len(cookable) == 0
    assert status["Pasta"]["status"] == "unavailable"

    # 2. Add ingredients for Omelette: eggs and butter
    agent.add_item("eggs", "food", 4.0, "pcs", 1.0, "fridge")
    agent.add_item("butter", "food", 50.0, "g", 10.0, "fridge")

    cookable, status = agent.what_can_we_cook()
    assert "Omelette" in cookable
    assert "Pasta" not in cookable
    assert status["Omelette"]["status"] == "available"
    assert status["Pasta"]["status"] == "unavailable"

    # 3. Add ingredients for Pasta: pasta, tomato sauce, garlic
    agent.add_item("pasta", "ingredient", 500.0, "g", 100.0, "pantry")
    agent.add_item("tomato sauce", "ingredient", 2.0, "cup", 1.0, "pantry")
    agent.add_item("garlic", "ingredient", 5.0, "clove", 1.0, "pantry")

    cookable, status = agent.what_can_we_cook()
    assert "Omelette" in cookable
    assert "Pasta" in cookable


def test_process_recipe_query() -> None:
    """Test process() query responses."""
    agent = InventoryAgent()
    agent.add_item("eggs", "food", 2.0, "pcs", 1.0, "fridge")
    agent.add_item("butter", "food", 20.0, "g", 5.0, "fridge")

    res = agent.process("What can we cook?")
    assert res["success"] is True
    assert "Omelette" in res["content"]

    res_list = agent.process("list inventory")
    assert res_list["success"] is True
    assert "eggs" in res_list["content"]
