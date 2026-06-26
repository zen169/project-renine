"""SQLAlchemy ORM model for Layer 3 — Smart Devices.

Stores discovered Home Assistant entity cache records.
"""
from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from renine.databases.models import MindBase


class SmartDevice(MindBase):
    """ORM model representing a cached smart home device entity.

    Home Assistant remains the ultimate source of truth; this model acts purely
    as a local read-only cache layer. No user-owned/manually created records may
    be stored in this table.

    Attributes:
        id: Auto-incrementing primary key.
        entity_id: Home Assistant entity ID (e.g. 'light.living_room'). Unique.
        name: Friendly name or description of the device.
        domain: Entity domain type (e.g. 'light', 'switch', 'sensor').
        state: Current cached state value (e.g. 'on', 'off', '21.5').
        attributes: JSON dict of Home Assistant state attributes.
        last_changed: UTC timestamp of last state change reported by HASS.
        last_updated: UTC timestamp of last update reported by HASS.
        last_synced: UTC timestamp of when this cache entry was last updated locally.
        created_at: UTC timestamp of record creation in the local cache database.
        updated_at: UTC timestamp of last local cache database modification.
    """

    __tablename__ = "smart_devices"
    __table_args__ = (
        Index("ix_smart_devices_entity_id", "entity_id", unique=True),
        Index("ix_smart_devices_domain", "domain"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
    )
    entity_id: Mapped[str] = mapped_column(
        String(256), nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(256), nullable=False,
    )
    domain: Mapped[str] = mapped_column(
        String(64), nullable=False,
    )
    state: Mapped[str] = mapped_column(
        String(128), nullable=False,
    )
    attributes: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict,
    )
    last_changed: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    last_updated: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    last_synced: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
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
            f"<SmartDevice id={self.id}"
            f" entity_id={self.entity_id!r}"
            f" domain={self.domain!r}"
            f" state={self.state!r}>"
        )
