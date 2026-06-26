"""SQLAlchemy ORM model for Layer 3 — Pending Smart Home Actions.

Stores in-flight confirmation requests for state-changing Home Assistant
service calls. Records are created when the agent detects a control intent
and expire after a configurable TTL (default 5 minutes).

Phase 7B constraint: No state-changing call may be issued without a
corresponding PendingSmartHomeAction row in status='pending'.
"""
from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from renine.databases.models import MindBase


class PendingSmartHomeAction(MindBase):
    """ORM model representing a pending confirmation for a device control action.

    Lifecycle:
        1. Created with status='pending' when the user issues a control command.
        2. Transitions to status='executed' after the HassClient service call succeeds.
        3. Transitions to status='expired' if expires_at is reached before confirmation.
        4. Transitions to status='cancelled' if the user rejects or issues a new command.

    Attributes:
        id: Auto-incrementing primary key.
        entity_id: Home Assistant entity ID targeted by the action.
        domain: HA domain (e.g. 'light', 'switch', 'fan', 'cover').
        service: HA service name (e.g. 'turn_on', 'turn_off', 'toggle').
        service_data: Optional extra payload forwarded to the service call.
        requested_at: UTC timestamp when the action was first requested.
        expires_at: UTC timestamp after which this action is invalid.
        status: Current lifecycle state ('pending', 'executed', 'expired', 'cancelled').
    """

    __tablename__ = "pending_smart_home_actions"
    __table_args__ = (
        Index("ix_pending_smart_home_actions_entity_id", "entity_id"),
        Index("ix_pending_smart_home_actions_status", "status"),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True,
    )
    entity_id: Mapped[str] = mapped_column(
        String(256), nullable=False,
    )
    domain: Mapped[str] = mapped_column(
        String(64), nullable=False,
    )
    service: Mapped[str] = mapped_column(
        String(64), nullable=False,
    )
    service_data: Mapped[dict[str, Any]] = mapped_column(
        JSON, nullable=False, default=dict,
    )
    requested_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending",
    )

    def is_expired(self) -> bool:
        """Return True if this action has passed its expiry timestamp."""
        now = datetime.datetime.now(datetime.timezone.utc)
        expires_at = self.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
        return now >= expires_at

    def __repr__(self) -> str:
        """Return a debug-friendly representation."""
        return (
            f"<PendingSmartHomeAction id={self.id}"
            f" entity_id={self.entity_id!r}"
            f" service={self.domain}.{self.service}"
            f" status={self.status!r}>"
        )
