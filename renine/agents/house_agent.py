"""House agent for managing rooms, appliances, and furniture.

Provides CRUD operations on house items and supports queries such as
'What appliances are in the kitchen?'
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from renine.agents.base_agent import AgentManifest, BaseAgent, MemoryAccessLevel
from renine.core.logging_config import get_logger
from renine.databases.models.house import HouseItem
from renine.databases.session import get_session
from renine.tools.permissions import PermissionLevel

logger = get_logger(__name__)


class HouseAgent(BaseAgent):
    """Agent that manages household structure and items."""

    def __init__(self) -> None:
        """Initialize the HouseAgent."""
        super().__init__()

    def get_manifest(self) -> AgentManifest:
        """Return the capability manifest for the HouseAgent."""
        return AgentManifest(
            name="house",
            description="Manages rooms, appliances, and furniture",
            required_tools=[],
            memory_access_level=MemoryAccessLevel.FULL_ACCESS,
            permission_level=PermissionLevel.STANDARD,
            active_phase=3,
        )

    def process(
        self,
        user_input: str,
        context: list[dict[str, str]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process queries about rooms, appliances, and furniture.

        Args:
            user_input: The user query text.
            context: Optional conversation context.
            metadata: Optional additional metadata.

        Returns:
            Response dict with 'content', 'success', and source info.
        """
        try:
            query = user_input.lower().strip()

            # Pattern: "what appliances are in the [room]?"
            if "what appliances are in the" in query or "what appliance is in the" in query:
                # Extract room name
                room = user_input.split("in the")[-1].strip().strip("?.").lower()
                items = self.list_items(room=room, item_type="appliance")
                if not items:
                    content = f"No appliances found in the {room}."
                else:
                    content = f"Appliances in the {room}:\n" + "\n".join(
                        f"- {item.name} (Status: {item.status})"
                        for item in items
                    )
                return {
                    "content": content,
                    "success": True,
                    "items": [{"name": i.name, "status": i.status} for i in items],
                    "source_agent": "house",
                }

            # Pattern: "what items are in the [room]?"
            if "what items are in the" in query or "what is in the" in query:
                room = user_input.split("in the")[-1].strip().strip("?.").lower()
                items = self.list_items(room=room)
                if not items:
                    content = f"No items found in the {room}."
                else:
                    content = f"Items in the {room}:\n" + "\n".join(
                        f"- {item.name} ({item.item_type}, Status: {item.status})"
                        for item in items
                    )
                return {
                    "content": content,
                    "success": True,
                    "items": [
                        {"name": i.name, "type": i.item_type, "status": i.status}
                        for i in items
                    ],
                    "source_agent": "house",
                }

            if "list house" in query or "show house" in query:
                items = self.list_items()
                if not items:
                    content = "No household items found."
                else:
                    content = "Household Items:\n" + "\n".join(
                        f"- {item.name} ({item.item_type}) in {item.room} "
                        f"[{item.status}]"
                        for item in items
                    )
                return {
                    "content": content,
                    "success": True,
                    "items": [{"name": i.name, "room": i.room} for i in items],
                    "source_agent": "house",
                }

            return {
                "content": "I can help you manage rooms, appliances, and furniture in the house.",
                "success": True,
                "source_agent": "house",
            }

        except Exception as e:
            logger.exception("Error in HouseAgent processing")
            return {
                "content": "",
                "success": False,
                "error": str(e),
                "source_agent": "house",
            }

    def add_item(
        self,
        name: str,
        item_type: str,
        room: str,
        status: str = "functional",
        details: dict[str, Any] | None = None,
    ) -> HouseItem:
        """Add a new item to the house database.

        Args:
            name: Name of the item (e.g. 'Fridge').
            item_type: Type of item ('room', 'appliance', 'furniture').
            room: Location of the item (e.g. 'Kitchen').
            status: Current operational status.
            details: Optional JSON dict of item details.

        Returns:
            The created HouseItem ORM object.
        """
        db = get_session("mind_db")
        try:
            # Check if it already exists
            stmt = select(HouseItem).where(HouseItem.name == name)
            item = db.scalars(stmt).first()
            if item:
                item.item_type = item_type
                item.room = room
                item.status = status
                if details is not None:
                    item.details = details
            else:
                item = HouseItem(
                    name=name,
                    item_type=item_type,
                    room=room,
                    status=status,
                    details=details or {},
                )
                db.add(item)
            db.commit()
            db.refresh(item)
            logger.info("Added house item: %s in %s", name, room)
            return item
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get_item(self, name: str) -> HouseItem | None:
        """Retrieve a house item by name.

        Args:
            name: Name of the item.

        Returns:
            The HouseItem ORM object or None if not found.
        """
        db = get_session("mind_db")
        try:
            stmt = select(HouseItem).where(HouseItem.name == name)
            return db.scalars(stmt).first()
        finally:
            db.close()

    def update_item(
        self,
        name: str,
        item_type: str | None = None,
        room: str | None = None,
        status: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> HouseItem | None:
        """Update an existing house item.

        Args:
            name: Name of the item to update.
            item_type: Optional new item type.
            room: Optional new room location.
            status: Optional new status.
            details: Optional new details dict.

        Returns:
            The updated HouseItem ORM object or None if not found.
        """
        db = get_session("mind_db")
        try:
            stmt = select(HouseItem).where(HouseItem.name == name)
            item = db.scalars(stmt).first()
            if not item:
                return None

            if item_type is not None:
                item.item_type = item_type
            if room is not None:
                item.room = room
            if status is not None:
                item.status = status
            if details is not None:
                item.details = details

            db.commit()
            db.refresh(item)
            logger.info("Updated house item: %s", name)
            return item
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def delete_item(self, name: str) -> bool:
        """Delete a house item by name.

        Args:
            name: Name of the item to delete.

        Returns:
            True if deleted, False if not found.
        """
        db = get_session("mind_db")
        try:
            stmt = select(HouseItem).where(HouseItem.name == name)
            item = db.scalars(stmt).first()
            if not item:
                return False
            db.delete(item)
            db.commit()
            logger.info("Deleted house item: %s", name)
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def list_items(
        self,
        room: str | None = None,
        item_type: str | None = None,
    ) -> list[HouseItem]:
        """List all house items, optionally filtered by room and/or item type.

        Args:
            room: Optional room filter (case-insensitive).
            item_type: Optional item type filter.

        Returns:
            List of HouseItem ORM objects.
        """
        db = get_session("mind_db")
        try:
            stmt = select(HouseItem)
            # Filter rooms case-insensitively
            if room:
                stmt = stmt.where(HouseItem.room.ilike(room))
            if item_type:
                stmt = stmt.where(HouseItem.item_type == item_type)
            return list(db.scalars(stmt).all())
        finally:
            db.close()
