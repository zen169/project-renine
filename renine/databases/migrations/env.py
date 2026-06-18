"""Alembic environment configuration for multi-database migrations.

Configures database connections and model metadata dynamically from the
Renine settings YAML configuration.
"""
from __future__ import annotations

import logging
import re
from logging.config import fileConfig
from typing import Any

from sqlalchemy import engine_from_config, pool

from alembic import context
from renine.core.config import get_project_root, get_settings
from renine.databases.models import HistoryBase, MindBase, PersonalityBase

# This is the Alembic Config object
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
logger = logging.getLogger("alembic.env")

db_names = config.get_main_option("databases", "")

# Associate bases with database keys
target_metadata = {
    "history": HistoryBase.metadata,
    "mind": MindBase.metadata,
    "personality": PersonalityBase.metadata,
}

# Mapping from database key to settings config key
_DB_MAPPING = {
    "history": "history_db",
    "mind": "mind_db",
    "personality": "personality_db",
}


def _get_db_url(name: str) -> str:
    """Resolve database URL dynamically from config/settings.yaml.

    Args:
        name: The database engine name (history, mind, or personality).

    Returns:
        The SQLite connection URL.
    """
    settings = get_settings()
    config_key = _DB_MAPPING.get(name)
    if not config_key:
        msg = f"Unknown database name: {name}"
        raise ValueError(msg)

    db_path_rel = settings.get("databases", {}).get(config_key)
    if not db_path_rel:
        msg = f"Database path config not found for key: {config_key}"
        raise KeyError(msg)

    project_root = get_project_root()
    db_path = (project_root / db_path_rel).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path.as_posix()}"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    for name in re.split(r",\s*", db_names):
        logger.info("Migrating database %s (offline)", name)
        url = _get_db_url(name)
        file_ = f"{name}.sql"
        logger.info("Writing output to %s", file_)
        with open(file_, "w") as buffer:
            context.configure(
                url=url,
                output_buffer=buffer,
                target_metadata=target_metadata.get(name),
                literal_binds=True,
                dialect_opts={"paramstyle": "named"},
            )
            with context.begin_transaction():
                context.run_migrations(engine_name=name)


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    engines = {}
    for name in re.split(r",\s*", db_names):
        url = _get_db_url(name)
        section = context.config.get_section(name, {})
        section["sqlalchemy.url"] = url
        engines[name] = rec = {}
        rec["engine"] = engine_from_config(
            section,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

    for name, rec in engines.items():
        engine = rec["engine"]
        rec["connection"] = conn = engine.connect()
        rec["transaction"] = conn.begin()

    try:
        for name, rec in engines.items():
            logger.info("Migrating database %s (online)", name)
            context.configure(
                connection=rec["connection"],
                upgrade_token=f"{name}_upgrades",
                downgrade_token=f"{name}_downgrades",
                target_metadata=target_metadata.get(name),
            )
            context.run_migrations(engine_name=name)

        for rec in engines.values():
            rec["transaction"].commit()
    except Exception:
        for rec in engines.values():
            rec["transaction"].rollback()
        raise
    finally:
        for rec in engines.values():
            rec["connection"].close()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
