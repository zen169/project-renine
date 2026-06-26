"""Database models — SQLAlchemy ORM models for all structured data.

Provides declarative bases and ORM models for all three databases:
- HistoryBase / Conversation (Layer 2)
- MindBase / MindRecord (Layer 3)
- PersonalityBase / Person (Layer 4)
"""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class HistoryBase(DeclarativeBase):
    """Declarative base class for Layer 2 history database."""


class MindBase(DeclarativeBase):
    """Declarative base class for Layer 3 mind database."""


class PersonalityBase(DeclarativeBase):
    """Declarative base class for Layer 4 personality database."""


# Import model classes to register them with the metadata
from renine.databases.models.conversation import Conversation
from renine.databases.models.mind import MindRecord
from renine.databases.models.personality import Person
from renine.databases.models.inventory import InventoryItem
from renine.databases.models.pets import Pet
from renine.databases.models.house import HouseItem
from renine.databases.models.file_index import FileIndex
from renine.databases.models.smart_device import SmartDevice
from renine.databases.models.pending_smart_home_action import PendingSmartHomeAction

__all__ = [
    "HistoryBase",
    "MindBase",
    "PersonalityBase",
    "Conversation",
    "MindRecord",
    "Person",
    "InventoryItem",
    "Pet",
    "HouseItem",
    "FileIndex",
    "SmartDevice",
    "PendingSmartHomeAction",
]
