"""Inventory agent for managing food, ingredients, and supplies.

Handles CRUD operations on inventory items, listings, and queries
like 'What can we cook?' based on available ingredients.
"""
from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import delete, select

from renine.agents.base_agent import AgentManifest, BaseAgent, MemoryAccessLevel
from renine.core.logging_config import get_logger
from renine.databases.models.inventory import InventoryItem
from renine.databases.session import get_session
from renine.tools.permissions import PermissionLevel

logger = get_logger(__name__)

RECIPES = {
    "Pasta": [
        {"name": "pasta", "quantity": 200.0, "unit": "g"},
        {"name": "tomato sauce", "quantity": 1.0, "unit": "cup"},
        {"name": "garlic", "quantity": 1.0, "unit": "clove"},
    ],
    "Omelette": [
        {"name": "eggs", "quantity": 2.0, "unit": "pcs"},
        {"name": "butter", "quantity": 10.0, "unit": "g"},
    ],
    "Pancakes": [
        {"name": "flour", "quantity": 100.0, "unit": "g"},
        {"name": "milk", "quantity": 200.0, "unit": "ml"},
        {"name": "eggs", "quantity": 1.0, "unit": "pcs"},
    ],
    "Salad": [
        {"name": "lettuce", "quantity": 100.0, "unit": "g"},
        {"name": "dressing", "quantity": 50.0, "unit": "ml"},
    ],
}


class InventoryAgent(BaseAgent):
    """Agent that manages household inventory and recipes."""

    def __init__(self) -> None:
        """Initialize the InventoryAgent."""
        super().__init__()

    def get_manifest(self) -> AgentManifest:
        """Return the capability manifest for the InventoryAgent."""
        return AgentManifest(
            name="inventory",
            description="Manages food, ingredients, and supply inventory",
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
        """Process natural language requests or structured queries.

        Args:
            user_input: The user's query or command.
            context: Optional conversation context.
            metadata: Optional additional metadata.

        Returns:
            Dictionary containing 'content', 'success', and source info.
        """
        try:
            query = user_input.lower().strip()
            if "what can we cook" in query or "what to cook" in query:
                cookable, recipes_status = self.what_can_we_cook()
                if cookable:
                    content = (
                        "Based on your current inventory, you can cook:\n"
                        + "\n".join(f"- {recipe}" for recipe in cookable)
                    )
                else:
                    content = "You don't have enough ingredients to cook the recipes on file."
                return {
                    "content": content,
                    "success": True,
                    "cookable": cookable,
                    "recipes_status": recipes_status,
                    "source_agent": "inventory",
                }

            if "list inventory" in query or "show inventory" in query:
                items = self.list_items()
                if not items:
                    content = "Your inventory is currently empty."
                else:
                    content = "Current Inventory:\n" + "\n".join(
                        f"- {item.name}: {item.quantity} {item.unit} "
                        f"(Location: {item.location})"
                        for item in items
                    )
                return {
                    "content": content,
                    "success": True,
                    "items": [
                        {"name": item.name, "quantity": item.quantity}
                        for item in items
                    ],
                    "source_agent": "inventory",
                }

            return {
                "content": "I can help you manage your inventory or tell you what we can cook.",
                "success": True,
                "source_agent": "inventory",
            }

        except Exception as e:
            logger.exception("Error in InventoryAgent processing")
            return {
                "content": "",
                "success": False,
                "error": str(e),
                "source_agent": "inventory",
            }

    def add_item(
        self,
        name: str,
        category: str,
        quantity: float,
        unit: str,
        threshold: float,
        location: str,
        expiration_date: datetime.datetime | None = None,
    ) -> InventoryItem:
        """Add a new item to the inventory.

        Args:
            name: Name of the item.
            category: Category (e.g. 'food', 'ingredient', 'supply').
            quantity: Current quantity in stock.
            unit: Unit of measure.
            threshold: Alert threshold.
            location: Storage location.
            expiration_date: Optional expiration date.

        Returns:
            The created InventoryItem ORM object.
        """
        db = get_session("mind_db")
        try:
            # Check if it already exists
            stmt = select(InventoryItem).where(InventoryItem.name == name)
            item = db.scalars(stmt).first()
            if item:
                item.quantity += quantity
                item.category = category
                item.unit = unit
                item.threshold = threshold
                item.location = location
                item.expiration_date = expiration_date
            else:
                item = InventoryItem(
                    name=name,
                    category=category,
                    quantity=quantity,
                    unit=unit,
                    threshold=threshold,
                    location=location,
                    expiration_date=expiration_date,
                )
                db.add(item)
            db.commit()
            db.refresh(item)
            logger.info("Added inventory item: %s", name)
            return item
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get_item(self, name: str) -> InventoryItem | None:
        """Retrieve an item from the inventory by name.

        Args:
            name: Name of the item.

        Returns:
            The InventoryItem ORM object or None.
        """
        db = get_session("mind_db")
        try:
            stmt = select(InventoryItem).where(InventoryItem.name == name)
            return db.scalars(stmt).first()
        finally:
            db.close()

    def update_item(
        self,
        name: str,
        quantity: float | None = None,
        category: str | None = None,
        unit: str | None = None,
        threshold: float | None = None,
        location: str | None = None,
        expiration_date: datetime.datetime | None = None,
    ) -> InventoryItem | None:
        """Update an existing inventory item.

        Args:
            name: Name of the item to update.
            quantity: Optional new quantity.
            category: Optional new category.
            unit: Optional new unit of measure.
            threshold: Optional new threshold.
            location: Optional new location.
            expiration_date: Optional new expiration date.

        Returns:
            The updated InventoryItem ORM object or None if not found.
        """
        db = get_session("mind_db")
        try:
            stmt = select(InventoryItem).where(InventoryItem.name == name)
            item = db.scalars(stmt).first()
            if not item:
                return None

            if quantity is not None:
                item.quantity = quantity
            if category is not None:
                item.category = category
            if unit is not None:
                item.unit = unit
            if threshold is not None:
                item.threshold = threshold
            if location is not None:
                item.location = location
            if expiration_date is not None:
                item.expiration_date = expiration_date

            db.commit()
            db.refresh(item)
            logger.info("Updated inventory item: %s", name)
            return item
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def delete_item(self, name: str) -> bool:
        """Delete an inventory item by name.

        Args:
            name: Name of the item to delete.

        Returns:
            True if the item was deleted, False if not found.
        """
        db = get_session("mind_db")
        try:
            stmt = select(InventoryItem).where(InventoryItem.name == name)
            item = db.scalars(stmt).first()
            if not item:
                return False
            db.delete(item)
            db.commit()
            logger.info("Deleted inventory item: %s", name)
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def list_items(self, category: str | None = None) -> list[InventoryItem]:
        """List all inventory items, optionally filtered by category.

        Args:
            category: Optional category filter.

        Returns:
            List of InventoryItem ORM objects.
        """
        db = get_session("mind_db")
        try:
            stmt = select(InventoryItem)
            if category:
                stmt = stmt.where(InventoryItem.category == category)
            return list(db.scalars(stmt).all())
        finally:
            db.close()

    def what_can_we_cook(self) -> tuple[list[str], dict[str, Any]]:
        """Determine what recipes can be cooked based on current inventory.

        Returns:
            A tuple containing:
              - List of names of cookable recipes.
              - Dict indicating status details for each recipe.
        """
        db = get_session("mind_db")
        try:
            # Load all items from inventory to memory for fast checking
            stmt = select(InventoryItem)
            items = db.scalars(stmt).all()
            inventory_map = {item.name.lower(): item for item in items}

            cookable = []
            recipes_status = {}

            for recipe_name, ingredients in RECIPES.items():
                missing_ingredients = []
                insufficient_ingredients = []
                for ing in ingredients:
                    ing_name = ing["name"].lower()
                    req_qty = ing["quantity"]
                    item = inventory_map.get(ing_name)

                    if not item:
                        missing_ingredients.append(ing["name"])
                    elif item.quantity < req_qty:
                        insufficient_ingredients.append({
                            "name": ing["name"],
                            "required": req_qty,
                            "available": item.quantity,
                            "unit": item.unit,
                        })

                if not missing_ingredients and not insufficient_ingredients:
                    cookable.append(recipe_name)
                    recipes_status[recipe_name] = {"status": "available"}
                else:
                    recipes_status[recipe_name] = {
                        "status": "unavailable",
                        "missing": missing_ingredients,
                        "insufficient": insufficient_ingredients,
                    }

            return cookable, recipes_status
        finally:
            db.close()
