"""SQLAlchemy model for Layer 3 — Mind Database.

Generic fact store with a ``namespace`` column that maps to the
Layer 3 namespaces defined in config/memory.yaml. Domain-specific
models (inventory, pets, house, etc.) with full schemas are
Phase 3 deliverables; this generic model supports Phase 2 CRUD
and semantic retrieval across all namespaces.

Inputs:
    - Structured facts from agents via MemoryManager.

Outputs:
    - ORM model for the ``mind_records`` table in mind.db.
"""
from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from renine.databases.models import MindBase


class MindRecord(MindBase):
    """Generic fact record in the mind database.

    Each record belongs to a namespace (e.g. ``inventory``,
    ``pets``, ``calendar_events``) and stores its data as
    a JSON payload. This allows Phase 2 to support all namespace
    operations while Phase 3 adds specialised schemas.

    Attributes:
        id: Auto-incrementing primary key.
        namespace: Logical namespace (e.g. ``inventory``).
        key: Short identifier within the namespace.
        value: JSON payload with the fact's structured data.
        summary: Human-readable summary for display / search.
        created_at: UTC timestamp of record creation.
        updated_at: UTC timestamp of last modification.
    """

    __tablename__ = "mind_records"
    __table_args__ = (
        Index("ix_mind_namespace", "namespace"),
        Index("ix_mind_namespace_key", "namespace", "key", unique=True),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
    )
    namespace: Mapped[str] = mapped_column(
        String(64), nullable=False,
    )
    key: Mapped[str] = mapped_column(
        String(256), nullable=False,
    )
    value: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict,
    )
    summary: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    def __repr__(self) -> str:
        """Return a debug-friendly representation."""
        return (
            f"<MindRecord id={self.id}"
            f" ns={self.namespace}"
            f" key={self.key!r}>"
        )
