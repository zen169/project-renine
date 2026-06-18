"""Memory agent for context retrieval and storage coordination.

Interacts with the MemoryManager to retrieve history, structured facts, and
people profiles relevant to the current conversation turn.
"""
from __future__ import annotations

import logging
from typing import Any

from renine.agents.base_agent import AgentManifest, BaseAgent, MemoryAccessLevel
from renine.memory.memory_manager import MemoryManager
from renine.tools.permissions import PermissionLevel

logger = logging.getLogger("renine.agents.memory_agent")


class MemoryAgent(BaseAgent):
    """Agent responsible for context retrieval and memory operations."""

    def __init__(self, memory_manager: MemoryManager | None = None) -> None:
        """Initialize the MemoryAgent.

        Args:
            memory_manager: Optional MemoryManager (for dependency injection).
        """
        self.memory_manager = memory_manager or MemoryManager()
        super().__init__()

    def get_manifest(self) -> AgentManifest:
        """Return the capability manifest for the MemoryAgent."""
        return AgentManifest(
            name="memory",
            description="Manages context retrieval, facts, and profile retrieval",
            required_tools=[],
            memory_access_level=MemoryAccessLevel.FULL_ACCESS,
            permission_level=PermissionLevel.STANDARD,
            active_phase=2,
        )

    def process(
        self,
        user_input: str,
        context: list[dict[str, str]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process a retrieval request by searching across Layers 2, 3, and 4.

        Args:
            user_input: The search query / user utterance.
            context: Not used.
            metadata: Optional search parameters.

        Returns:
            Dictionary containing 'content' (formatted context) and 'success'.
        """
        try:
            limit = metadata.get("limit", 3) if metadata else 3
            history_blocks = []
            recent_convs = self.memory_manager.get_recent_conversations(
                limit=limit,
            )
            for conv in recent_convs:
                history_blocks.append(f"- {conv['date']}: {conv['summary']}")

            fact_blocks = []
            namespaces = [
                "inventory",
                "pets",
                "calendar_events",
                "house",
                "bills",
                "tasks",
                "notes",
                "file_index",
                "daily_routines",
                "shopping_lists",
            ]
            for ns in namespaces:
                results = self.memory_manager.search_facts(
                    ns, user_input, limit=2,
                )
                for r in results:
                    if r.get("distance", 0.0) < 1.5:
                        fact_blocks.append(f"- [{ns}] {r['summary']}")

            people_blocks = []
            people = self.memory_manager.search_people(user_input, limit=2)
            for p in people:
                if p.get("distance", 0.0) < 1.5:
                    people_blocks.append(
                        f"- Person: {p['name']} ({p['relationship']}) - "
                        f"Notes: {p['notes']}",
                    )

            sections = []
            if history_blocks:
                sections.append(
                    "Recent Conversation History:\n"
                    + "\n".join(history_blocks),
                )
            if fact_blocks:
                sections.append("Relevant Facts:\n" + "\n".join(fact_blocks))
            if people_blocks:
                sections.append(
                    "Relevant People Profiles:\n" + "\n".join(people_blocks),
                )

            content = (
                "\n\n".join(sections)
                if sections
                else "No relevant memories found."
            )

            return {
                "content": content,
                "success": True,
                "source_agent": "memory",
            }

        except Exception as e:
            logger.exception("Error in MemoryAgent processing")
            return {
                "content": "",
                "success": False,
                "error": str(e),
                "source_agent": "memory",
            }
