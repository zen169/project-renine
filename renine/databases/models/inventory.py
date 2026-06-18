"""SQLAlchemy ORM model for Layer 3 — Inventory.

Stores items in the household inventory (food, ingredients, supplies).
Includes quantity, unit-of-measure, and alert thresholds.
"""
from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from renine.databases.models import MindBase


class InventoryItem(MindBase):
    """ORM model representing an item in the household inventory.

    Attributes:
        id: Auto-incrementing primary key.
        name: Unique name of the item.
        category: Category of the item (e.g., 'food', 'ingredient', 'supply').
        quantity: Current quantity in stock.
        unit: Unit of measure (e.g., 'kg', 'grams', 'pieces', 'liters').
        threshold: Minimum quantity threshold for alerts/shopping.
        location: Where it is stored (e.g., 'fridge', 'pantry').
        expiration_date: Date when the item expires (nullable).
        created_at: UTC timestamp of record creation.
        updated_at: UTC timestamp of last modification.
    """

    __tablename__ = "inventory"
    __table_args__ = (
        Index("ix_inventory_name", "name", unique=True),
        Index("ix_inventory_category", "category"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
    )
    name: Mapped[str] = mapped_column(
        String(128), nullable=False,
    )
    category: Mapped[str] = mapped_column(
        String(64), nullable=False, default="supply",
    )
    quantity: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
    )
    unit: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pcs",
    )
    threshold: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
    )
    location: Mapped[str] = mapped_column(
        String(128), nullable=False, default="",
    )
    expiration_date: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
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
            f"<InventoryItem id={self.id}"
            f" name={self.name!r}"
            f" quantity={self.quantity}"
            f" unit={self.unit!r}>"
        )
