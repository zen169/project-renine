"""SQLAlchemy model for Layer 2 conversation history.

Stores summarized conversation sessions with raw turn JSON and a
48-hour TTL enforced by the expiration module.

Schema (from master prompt):
    conversations(id, date, summary TEXT, raw_turns JSON, created_at TIMESTAMP)

Inputs:
    - Conversation sessions from the memory manager.

Outputs:
    - ORM model for the ``conversations`` table in history.db.
"""
from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import Date, DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from renine.databases.models import HistoryBase


class Conversation(HistoryBase):
    """ORM model representing a completed conversation session.

    Attributes:
        id: Auto-incrementing primary key.
        date: Date of the conversation (date only, no time).
        summary: Short text summary of the conversation.
        raw_turns: Full JSON list of turn dicts (role + content).
        created_at: UTC timestamp of session creation.
    """

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
    )
    date: Mapped[datetime.date] = mapped_column(
        Date,
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc).date(),
    )
    summary: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
    )
    raw_turns: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    def __repr__(self) -> str:
        """Return a debug-friendly representation."""
        return (
            f"<Conversation id={self.id}"
            f" date={self.date}"
            f" created_at={self.created_at.isoformat()}>"
        )
