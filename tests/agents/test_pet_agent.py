"""Tests for the PetAgent."""
from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

import pytest

from renine.agents.base_agent import MemoryAccessLevel
from renine.agents.pet_agent import PetAgent
from renine.core.events import event_bus
from renine.databases.models import MindBase
from renine.databases.session import _engines, _sessionmakers, get_engine
from renine.memory.expiration import get_scheduler


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

    # Clean up jobs in scheduler
    scheduler = get_scheduler()
    scheduler.remove_all_jobs()
    if scheduler.running:
        scheduler.shutdown(wait=False)

    _engines.clear()
    _sessionmakers.clear()
    if os.path.exists(temp_db_path):
        try:
            os.remove(temp_db_path)
        except OSError:
            pass


def test_pet_agent_manifest() -> None:
    """Test the agent manifest declarations."""
    agent = PetAgent()
    manifest = agent.get_manifest()
    assert manifest.name == "pets"
    assert manifest.memory_access_level == MemoryAccessLevel.FULL_ACCESS


def test_pet_agent_crud() -> None:
    """Test CRUD operations on pet profiles."""
    agent = PetAgent()

    # Create
    pet = agent.add_pet(
        name="Buddy",
        species="dog",
        breed="Golden Retriever",
        age=3.0,
        feeding_schedule=[{"time": "08:00", "amount": "1 cup"}],
    )
    assert pet.id is not None
    assert pet.name == "Buddy"
    assert pet.age == 3.0

    # Retrieve
    retrieved = agent.get_pet("Buddy")
    assert retrieved is not None
    assert retrieved.breed == "Golden Retriever"

    # Update
    updated = agent.update_pet("Buddy", age=4.0, weight=30.0)
    assert updated is not None
    assert updated.age == 4.0
    assert updated.weight == 30.0

    # List
    pets = agent.list_pets()
    assert len(pets) == 1
    assert pets[0].name == "Buddy"

    # Delete
    deleted = agent.delete_pet("Buddy")
    assert deleted is True
    assert agent.get_pet("Buddy") is None


def test_feeding_tracking() -> None:
    """Test recording feeding logs."""
    agent = PetAgent()
    agent.add_pet("Buddy", "dog")

    assert agent.get_pet("Buddy").last_fed is None

    success = agent.feed_pet("Buddy")
    assert success is True

    buddy = agent.get_pet("Buddy")
    assert buddy.last_fed is not None


def test_pet_reminders_scheduling_and_firing() -> None:
    """Test that pet feeding schedules add jobs and trigger the event bus."""
    agent = PetAgent()

    # Register a callback on the event bus to verify event firing
    fired_payload = None

    def on_reminder(payload: dict[str, Any]) -> None:
        nonlocal fired_payload
        fired_payload = payload

    event_bus.subscribe("pet.feeding_reminder", on_reminder)

    try:
        # Add pet with a feeding schedule
        agent.add_pet(
            name="Max",
            species="cat",
            feeding_schedule=[{"time": "12:00", "amount": "0.5 cup"}],
        )

        scheduler = get_scheduler()
        jobs = scheduler.get_jobs()

        # Verify job is scheduled in APScheduler
        job_exists = any(job.id == "pet_feed_Max_0" for job in jobs)
        assert job_exists is True

        # Find and trigger the scheduled job manually
        job = next(job for job in jobs if job.id == "pet_feed_Max_0")
        job.func(*job.args, **job.kwargs)

        # Assert event bus published the reminder event
        assert fired_payload is not None
        assert fired_payload["pet_name"] == "Max"
        assert fired_payload["time"] == "12:00"
        assert fired_payload["amount"] == "0.5 cup"

    finally:
        event_bus.unsubscribe("pet.feeding_reminder", on_reminder)
