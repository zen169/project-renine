"""Database session management for Renine.

Creates engine and session factories for each of the three local SQLite
databases: history, mind, and personality.

Inputs:
    - config/settings.yaml for database paths.

Outputs:
    - Session factories and engine instances for each database.
"""
from __future__ import annotations

from typing import Any
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from renine.core.config import get_project_root, get_settings

# Cache engines and sessionmakers to avoid re-creation
_engines: dict[str, Engine] = {}
_sessionmakers: dict[str, sessionmaker[Session]] = {}


def _setup_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
    """Enable foreign key constraints and WAL mode for SQLite connections."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def get_engine(db_key: str) -> Engine:
    """Get or create the SQLAlchemy engine for the specified database key.

    Args:
        db_key: Config key under 'databases' (history_db, mind_db, personality_db).

    Returns:
        Configured SQLAlchemy Engine.
    """
    if db_key in _engines:
        return _engines[db_key]

    settings = get_settings()
    db_path_rel = settings.get("databases", {}).get(db_key)
    if not db_path_rel:
        msg = f"Database path config not found for key: {db_key}"
        raise KeyError(msg)

    project_root = get_project_root()
    db_path = (project_root / db_path_rel).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db_url = f"sqlite:///{db_path.as_posix()}"
    engine = create_engine(db_url, echo=False)

    event.listen(engine, "connect", _setup_sqlite_pragma)

    _engines[db_key] = engine
    return engine


def get_sessionmaker(db_key: str) -> sessionmaker[Session]:
    """Get or create the sessionmaker factory for the specified database key.

    Args:
        db_key: Config key under 'databases' (history_db, mind_db, personality_db).

    Returns:
        Configured sessionmaker factory.
    """
    if db_key in _sessionmakers:
        return _sessionmakers[db_key]

    engine = get_engine(db_key)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    _sessionmakers[db_key] = factory
    return factory


def get_session(db_key: str) -> Session:
    """Get a new SQLAlchemy database session for the specified database key.

    Args:
        db_key: Config key under 'databases' (history_db, mind_db, personality_db).

    Returns:
        A new SQLAlchemy Session.
    """
    factory = get_sessionmaker(db_key)
    return factory()
