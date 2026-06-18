"""Layer 2 memory: conversation history management.

Provides persistence for conversation sessions using the history.db SQLite
database.
"""
from __future__ import annotations

import datetime
import logging
# Import select and delete from sqlalchemy
from sqlalchemy import delete, select
from typing import Any

from renine.databases.models.conversation import Conversation
from renine.databases.session import get_session

logger = logging.getLogger("renine.memory.layer2_history")


def store_conversation(
    summary: str,
    raw_turns: list[dict[str, Any]],
    date: datetime.date | None = None,
) -> Conversation:
    """Store a completed conversation session in the history database.

    Args:
        summary: A short text summary of the conversation.
        raw_turns: Full JSON-serializable list of turns.
        date: The date of the conversation. Defaults to today (UTC).

    Returns:
        The stored Conversation ORM model.
    """
    if date is None:
        date = datetime.datetime.now(datetime.timezone.utc).date()

    db = get_session("history_db")
    try:
        conv = Conversation(
            summary=summary,
            raw_turns=raw_turns,
            date=date,
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        logger.info("Stored conversation ID %d in history.db", conv.id)
        return conv
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_conversations_by_date(date: datetime.date) -> list[Conversation]:
    """Retrieve all conversations matching the specified date.

    Args:
        date: The date to search for.

    Returns:
        List of matching Conversation models.
    """
    db = get_session("history_db")
    try:
        stmt = select(Conversation).where(Conversation.date == date)
        return list(db.scalars(stmt).all())
    finally:
        db.close()


def get_recent_conversations(limit: int = 10) -> list[Conversation]:
    """Retrieve recent conversations sorted by creation time descending.

    Args:
        limit: Max number of conversations to retrieve.

    Returns:
        List of recent Conversation models.
    """
    db = get_session("history_db")
    try:
        stmt = (
            select(Conversation)
            .order_by(Conversation.created_at.desc())
            .limit(limit)
        )
        return list(db.scalars(stmt).all())
    finally:
        db.close()


def get_conversation(id_: int) -> Conversation | None:
    """Retrieve a single conversation by its primary key ID.

    Args:
        id_: The primary key ID.

    Returns:
        The Conversation model if found, else None.
    """
    db = get_session("history_db")
    try:
        return db.get(Conversation, id_)
    finally:
        db.close()


def delete_expired_conversations(ttl_hours: int = 48) -> int:
    """Delete conversations created more than ttl_hours ago.

    Args:
        ttl_hours: The expiration age threshold in hours.

    Returns:
        The number of deleted records.
    """
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
        hours=ttl_hours,
    )
    db = get_session("history_db")
    try:
        stmt = delete(Conversation).where(Conversation.created_at < cutoff)
        res = db.execute(stmt)
        db.commit()
        deleted_count = res.rowcount
        if deleted_count > 0:
            logger.info(
                "Deleted %d expired conversations from history.db",
                deleted_count,
            )
        return deleted_count
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
