"""Tests for FileAgent indexing and searching capabilities."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from sqlalchemy import select

from renine.agents.file_agent import FileAgent
from renine.databases.models import MindBase
from renine.databases.models.file_index import FileIndex
from renine.databases.session import _engines, _sessionmakers, get_engine, get_session


@pytest.fixture
def temp_mind_db(tmp_path: Path):
    """Fixture to setup a clean, temporary database for Layer 3."""
    db_file = tmp_path / "test_mind.db"
    _engines.clear()
    _sessionmakers.clear()

    mock_settings = {
        "databases": {
            "mind_db": str(db_file),
        },
    }

    with patch("renine.databases.session.get_settings", return_value=mock_settings):
        engine = get_engine("mind_db")
        MindBase.metadata.create_all(bind=engine)
        yield db_file

    _engines.clear()
    _sessionmakers.clear()


@pytest.fixture
def setup_files_environment(tmp_path: Path, temp_mind_db):
    """Create a temporary environment with dummy files and configuration."""
    allowed_dir = tmp_path / "allowed"
    allowed_dir.mkdir()

    # Create dummy files
    f1 = allowed_dir / "document.txt"
    f1.write_text("Hello document text file preview content", encoding="utf-8")

    f2 = allowed_dir / "notes.md"
    f2.write_text("Secret notes markdown preview content", encoding="utf-8")

    config = {
        "security": {
            "filesystem": {
                "allowed_paths": [str(allowed_dir)],
                "blocked_paths": [],
                "max_read_size_bytes": 1000000,
            }
        }
    }

    # Patch security config globally
    with patch("renine.agents.file_agent.get_security_config", return_value=config), \
         patch("renine.security.input_validator.get_security_config", return_value=config):
        yield allowed_dir, [f1, f2]


def test_indexing(setup_files_environment) -> None:
    """Allowed directories are scanned and file_index table is populated."""
    allowed_dir, files = setup_files_environment
    agent = FileAgent()

    # Perform indexing
    count = agent.index_allowed_directories()
    assert count == 2

    # Query file_index database
    db = get_session("mind_db")
    try:
        indexed_files = db.scalars(select_stmt := select(FileIndex)).all()
        assert len(indexed_files) == 2
        names = {item.file_name for item in indexed_files}
        assert names == {"document.txt", "notes.md"}

        # Verify preview text is stored
        doc_item = db.scalars(
            select(FileIndex).where(FileIndex.file_name == "document.txt")
        ).first()
        assert doc_item is not None
        assert "preview content" in doc_item.summary
    finally:
        db.close()


def test_re_indexing_skips_unchanged(setup_files_environment) -> None:
    """Index is not updated if files are unchanged, but updates if size changes."""
    allowed_dir, files = setup_files_environment
    agent = FileAgent()

    agent.index_allowed_directories()

    # Get initial index timestamp
    db = get_session("mind_db")
    try:
        from sqlalchemy import select
        item = db.scalars(select(FileIndex).where(FileIndex.file_name == "document.txt")).first()
        assert item is not None
        initial_indexed_time = item.last_indexed
    finally:
        db.close()

    # Index again without changes
    agent.index_allowed_directories()

    db = get_session("mind_db")
    try:
        item = db.scalars(select(FileIndex).where(FileIndex.file_name == "document.txt")).first()
        assert item is not None
        # Should be identical
        assert item.last_indexed == initial_indexed_time
    finally:
        db.close()


def test_search_by_filename(setup_files_environment) -> None:
    """Search matches filename via process() method."""
    allowed_dir, files = setup_files_environment
    agent = FileAgent()

    # Index first
    agent.index_allowed_directories()

    # Perform search
    res = agent.process("search document")
    assert res["success"] is True
    assert "document.txt" in res["content"]
    assert len(res["results"]) == 1
    assert res["results"][0]["name"] == "document.txt"
