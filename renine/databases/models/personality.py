"""SQLAlchemy model for Layer 4 — Personality Database.

Stores people profiles with relationships, preferences, and
personality data. Each person gets a single row; array fields
(food_preferences, hobbies, etc.) use JSON columns.

Schema (from master prompt):
    people(id, name, relationship, age, birthday, food_preferences JSON,
           hobbies JSON, personality_traits JSON, goals JSON, habits JSON,
           notes TEXT, created_at, updated_at)

Inputs:
    - Person profile data from agents via MemoryManager.

Outputs:
    - ORM model for the ``people`` table in personality.db.
"""
from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from renine.databases.models import PersonalityBase


class Person(PersonalityBase):
    """ORM model representing a person known to Renine.

    Attributes:
        id: Auto-incrementing primary key.
        name: Person's name (unique).
        relationship: Relationship to the household (e.g. ``owner``).
        age: Current age (nullable, updated manually).
        birthday: Birthday as ISO date string (nullable).
        food_preferences: JSON list of food preferences.
        hobbies: JSON list of hobbies.
        personality_traits: JSON list of personality descriptors.
        goals: JSON list of current goals.
        habits: JSON list of habits / routines.
        notes: Free-form text notes.
        created_at: UTC timestamp of record creation.
        updated_at: UTC timestamp of last modification.
    """

    __tablename__ = "people"
    __table_args__ = (
        Index("ix_people_name", "name", unique=True),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
    )
    name: Mapped[str] = mapped_column(
        String(128), nullable=False,
    )
    relationship: Mapped[str] = mapped_column(
        String(64), nullable=False, default="",
    )
    age: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    birthday: Mapped[str | None] = mapped_column(
        String(16), nullable=True,
    )
    food_preferences: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list,
    )
    hobbies: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list,
    )
    personality_traits: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list,
    )
    goals: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list,
    )
    habits: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list,
    )
    notes: Mapped[str] = mapped_column(
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
            f"<Person id={self.id}"
            f" name={self.name!r}"
            f" relationship={self.relationship!r}>"
        )
