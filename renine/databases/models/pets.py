"""SQLAlchemy ORM model for Layer 3 — Pets.

Stores pet profiles including breed, age, weight, feeding schedules,
medical conditions, active medications, and feeding tracking.
"""
from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from renine.databases.models import MindBase


class Pet(MindBase):
    """ORM model representing a household pet.

    Attributes:
        id: Auto-incrementing primary key.
        name: Name of the pet.
        species: Species of the pet (e.g., 'dog', 'cat').
        breed: Breed of the pet (nullable).
        age: Age of the pet in years (nullable).
        birthday: Birthday of the pet (nullable).
        weight: Weight in kg (nullable).
        feeding_schedule: JSON list of scheduled feeding times and details.
        medical_conditions: JSON list of medical conditions.
        medications: JSON list of active medications and schedules.
        last_fed: Date and time when the pet was last fed (nullable).
        created_at: UTC timestamp of record creation.
        updated_at: UTC timestamp of last modification.
    """

    __tablename__ = "pets"
    __table_args__ = (
        Index("ix_pets_name", "name", unique=True),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
    )
    name: Mapped[str] = mapped_column(
        String(128), nullable=False,
    )
    species: Mapped[str] = mapped_column(
        String(64), nullable=False,
    )
    breed: Mapped[str | None] = mapped_column(
        String(128), nullable=True,
    )
    age: Mapped[float | None] = mapped_column(
        Float, nullable=True,
    )
    birthday: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
    )
    weight: Mapped[float | None] = mapped_column(
        Float, nullable=True,
    )
    feeding_schedule: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list,
    )
    medical_conditions: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list,
    )
    medications: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list,
    )
    last_fed: Mapped[datetime.datetime | None] = mapped_column(
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
            f"<Pet id={self.id}"
            f" name={self.name!r}"
            f" species={self.species!r}>"
        )
