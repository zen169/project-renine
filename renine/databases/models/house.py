"""SQLAlchemy ORM model for Layer 3 — House.

Stores room, appliance, and furniture management data.
"""
from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from renine.databases.models import MindBase


class HouseItem(MindBase):
    """ORM model representing a room, appliance, or piece of furniture.

    Attributes:
        id: Auto-incrementing primary key.
        name: Name or description of the item (e.g., 'Kitchen Fridge').
        item_type: Type of item (e.g., 'room', 'appliance', 'furniture').
        room: The room where this item is located (e.g., 'Kitchen').
        status: Current status (e.g., 'functional', 'maintenance', 'broken').
        details: JSON dict of custom metadata (brand, model, purchase date, etc.).
        created_at: UTC timestamp of record creation.
        updated_at: UTC timestamp of last modification.
    """

    __tablename__ = "house"
    __table_args__ = (
        Index("ix_house_name", "name", unique=True),
        Index("ix_house_item_type", "item_type"),
        Index("ix_house_room", "room"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
    )
    name: Mapped[str] = mapped_column(
        String(128), nullable=False,
    )
    item_type: Mapped[str] = mapped_column(
        String(64), nullable=False,
    )
    room: Mapped[str] = mapped_column(
        String(128), nullable=False, default="General",
    )
    status: Mapped[str] = mapped_column(
        String(64), nullable=False, default="functional",
    )
    details: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict,
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
            f"<HouseItem id={self.id}"
            f" name={self.name!r}"
            f" type={self.item_type!r}"
            f" room={self.room!r}>"
        )
