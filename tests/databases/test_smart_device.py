"""Tests for SmartDevice model and its database schema."""
from __future__ import annotations

import datetime
import importlib.util
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import select

from renine.databases.models import MindBase
from renine.databases.models.smart_device import SmartDevice
from renine.databases.session import _engines, _sessionmakers, get_engine, get_session


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create a temporary SQLite database for testing the SmartDevice schema."""
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


def test_circular_imports_safe() -> None:
    """Ensure that we can import databases.models, SmartDevice, and MindBase safely."""
    # The fixture already imports them at the top level. We verify they exist.
    assert SmartDevice is not None
    assert MindBase is not None


def test_smart_device_crud(setup_test_db: str) -> None:
    """Test full CRUD capability for the SmartDevice model cache layer."""
    session = get_session("mind_db")
    
    # Create
    now = datetime.datetime.now(datetime.timezone.utc)
    device = SmartDevice(
        entity_id="light.living_room",
        name="Living Room Light",
        domain="light",
        state="off",
        attributes={"brightness": 255, "friendly_name": "Living Room Light"},
        last_changed=now - datetime.timedelta(minutes=10),
        last_updated=now - datetime.timedelta(minutes=5),
        last_synced=now,
    )
    session.add(device)
    session.commit()

    # Query / Read
    retrieved = session.execute(
        select(SmartDevice).where(SmartDevice.entity_id == "light.living_room")
    ).scalar_one_or_none()

    assert retrieved is not None
    assert retrieved.id is not None
    assert retrieved.entity_id == "light.living_room"
    assert retrieved.name == "Living Room Light"
    assert retrieved.domain == "light"
    assert retrieved.state == "off"
    assert retrieved.attributes == {"brightness": 255, "friendly_name": "Living Room Light"}
    assert retrieved.last_changed is not None
    assert retrieved.last_updated is not None
    assert retrieved.last_synced is not None
    assert retrieved.created_at is not None
    assert retrieved.updated_at is not None

    # Update
    retrieved.state = "on"
    retrieved.last_synced = datetime.datetime.now(datetime.timezone.utc)
    session.commit()

    updated = session.execute(
        select(SmartDevice).where(SmartDevice.entity_id == "light.living_room")
    ).scalar_one_or_none()
    assert updated is not None
    assert updated.state == "on"

    # Delete
    session.delete(updated)
    session.commit()

    deleted = session.execute(
        select(SmartDevice).where(SmartDevice.entity_id == "light.living_room")
    ).scalar_one_or_none()
    assert deleted is None


def test_migration_revision_pointers() -> None:
    """Verify that the manually created Alembic migration specifies correct revisions."""
    migration_dir = (
        Path(__file__).resolve().parents[2]
        / "renine"
        / "databases"
        / "migrations"
        / "versions"
    )
    
    # Locate our migration version file
    migration_files = list(migration_dir.glob("*_add_smart_devices_table.py"))
    assert len(migration_files) == 1
    file_path = migration_files[0]

    # Load migration module dynamically
    spec = importlib.util.spec_from_file_location("migration_module", str(file_path))
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    # Assert correctness of migration markers
    assert module.revision == "8fbc76e8a4d2"
    assert module.down_revision == "5de0768cf1f9"
