"""MemoryManager: Unified interface for all four layers of Renine Memory.

Acts as the single point of entry for storing and retrieving facts, context,
history, and profiles. Enforces security boundaries and access rules.
"""
from __future__ import annotations

import logging
from typing import Any

from renine.core.config import get_memory_config
from renine.memory import layer2_history, layer3_mind, layer4_personality
from renine.memory.layer1_context import ConversationContext

logger = logging.getLogger("renine.memory.memory_manager")


class MemoryManager:
    """Unified manager coordinating Layers 1-4 of Renine's memory system."""

    def __init__(self) -> None:
        """Initialize the memory manager and Layer 1 context."""
        config = get_memory_config()
        layer1_cfg = config.get("memory", {}).get("layer1", {})
        max_msgs = layer1_cfg.get("max_messages", 50)
        self._context = ConversationContext(max_messages=max_msgs)

    # --- Layer 1: Conversation Context ---

    def add_message(
        self,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Add a message to the active conversation session (Layer 1)."""
        self._context.add_message(role, content, metadata=metadata)

    def get_messages(self) -> list[dict[str, Any]]:
        """Get the current conversation turns."""
        return self._context.get_messages()

    def get_last_n_messages(self, n: int) -> list[dict[str, Any]]:
        """Get the N most recent message turns."""
        return self._context.get_last_n(n)

    def clear_context(self) -> None:
        """Clear the active conversation context."""
        self._context.clear()

    # --- Layer 2: Conversation History ---

    def persist_current_session(self, summary: str) -> None:
        """Persist current session turns to Layer 2 and clear context."""
        turns = self._context.get_messages()
        if not turns:
            logger.warning("No active turns to persist to history")
            return

        layer2_history.store_conversation(summary=summary, raw_turns=turns)
        self._context.clear()

    def get_recent_conversations(self, limit: int = 10) -> list[dict[str, Any]]:
        """Retrieve recent conversation summaries and turns from Layer 2."""
        convs = layer2_history.get_recent_conversations(limit=limit)
        return [
            {
                "id": c.id,
                "date": c.date.isoformat() if c.date else None,
                "summary": c.summary,
                "raw_turns": c.raw_turns,
                "created_at": c.created_at.isoformat(),
            }
            for c in convs
        ]

    # --- Layer 3: Mind Database ---

    def store_fact(
        self,
        namespace: str,
        key: str,
        value: dict[str, Any],
        summary: str,
    ) -> None:
        """Store a structured fact (Layer 3) in the mind database."""
        layer3_mind.store_fact(namespace, key, value, summary)

    def get_fact(self, namespace: str, key: str) -> dict[str, Any] | None:
        """Retrieve a structured fact from the mind database."""
        record = layer3_mind.get_fact(namespace, key)
        if not record:
            return None
        return {
            "key": record.key,
            "value": record.value,
            "summary": record.summary,
            "updated_at": record.updated_at.isoformat(),
        }

    def delete_fact(self, namespace: str, key: str) -> bool:
        """Delete a fact from the mind database."""
        return layer3_mind.delete_fact(namespace, key)

    def search_facts(
        self,
        namespace: str,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Perform semantic search on facts within a namespace."""
        return layer3_mind.search_facts(namespace, query, limit=limit)

    def list_facts(self, namespace: str) -> list[dict[str, Any]]:
        """List all facts within a namespace."""
        records = layer3_mind.list_facts(namespace)
        return [
            {
                "key": r.key,
                "value": r.value,
                "summary": r.summary,
                "updated_at": r.updated_at.isoformat(),
            }
            for r in records
        ]

    # --- Layer 4: Personality ---

    def store_person(
        self,
        name: str,
        relationship: str,
        age: int | None = None,
        birthday: str | None = None,
        food_preferences: list[str] | None = None,
        hobbies: list[str] | None = None,
        personality_traits: list[str] | None = None,
        goals: list[str] | None = None,
        habits: list[str] | None = None,
        notes: str = "",
    ) -> None:
        """Store or update a person profile (Layer 4)."""
        layer4_personality.store_person(
            name=name,
            relationship=relationship,
            age=age,
            birthday=birthday,
            food_preferences=food_preferences,
            hobbies=hobbies,
            personality_traits=personality_traits,
            goals=goals,
            habits=habits,
            notes=notes,
        )

    def get_person(self, name: str) -> dict[str, Any] | None:
        """Retrieve a person profile by name."""
        p = layer4_personality.get_person(name)
        if not p:
            return None
        return {
            "name": p.name,
            "relationship": p.relationship,
            "age": p.age,
            "birthday": p.birthday,
            "food_preferences": p.food_preferences,
            "hobbies": p.hobbies,
            "personality_traits": p.personality_traits,
            "goals": p.goals,
            "habits": p.habits,
            "notes": p.notes,
            "updated_at": p.updated_at.isoformat(),
        }

    def delete_person(self, name: str) -> bool:
        """Delete a person profile by name."""
        return layer4_personality.delete_person(name)

    def search_people(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """Perform semantic search on people profiles."""
        return layer4_personality.search_people(query, limit=limit)

    def list_people(self) -> list[dict[str, Any]]:
        """List all people profiles."""
        records = layer4_personality.list_people()
        return [
            {
                "name": p.name,
                "relationship": p.relationship,
                "age": p.age,
                "birthday": p.birthday,
                "food_preferences": p.food_preferences,
                "hobbies": p.hobbies,
                "personality_traits": p.personality_traits,
                "goals": p.goals,
                "habits": p.habits,
                "notes": p.notes,
                "updated_at": p.updated_at.isoformat(),
            }
            for p in records
        ]
