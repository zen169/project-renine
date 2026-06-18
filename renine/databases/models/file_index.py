"""SQLAlchemy model for Layer 3 — File Index table.

Stores metadata of files in allowed directories for fast lookup and search.
"""
from __future__ import annotations

import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from renine.databases.models import MindBase


class FileIndex(MindBase):
    """ORM Model for the 'file_index' table in mind.db.

    Attributes:
        id: Auto-incrementing primary key.
        file_path: Absolute path to the file.
        file_name: Name of the file.
        file_type: File extension (e.g. '.docx', '.pdf').
        file_size: File size in bytes.
        last_modified: Timestamp of last modification on disk.
        summary: Extracted text summary or head content of the file.
        last_indexed: Timestamp of last index.
    """

    __tablename__ = "file_index"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
    )
    file_path: Mapped[str] = mapped_column(
        String(1024), unique=True, nullable=False, index=True,
    )
    file_name: Mapped[str] = mapped_column(
        String(256), nullable=False, index=True,
    )
    file_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True,
    )
    file_size: Mapped[int] = mapped_column(
        Integer, nullable=False,
    )
    last_modified: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    summary: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
    )
    last_indexed: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    def __repr__(self) -> str:
        """Return a debug-friendly representation."""
        return f"<FileIndex id={self.id} path={self.file_path!r}>"
