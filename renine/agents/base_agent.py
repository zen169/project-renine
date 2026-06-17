"""Abstract base class for all Renine agents.

Every agent in the system inherits from BaseAgent, which enforces
a consistent interface for tool manifests, memory access levels,
and permission levels. This ensures all agents are forward-compatible
with the tool system, memory manager, and permission framework.

Inputs:
    - Agent name and configuration.
    - Tool manifest, memory access, and permission declarations.

Outputs:
    - Abstract interface that all agents must implement.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from renine.core.logging_config import get_logger
from renine.tools.permissions import PermissionLevel

logger = get_logger(__name__)


class MemoryAccessLevel(IntEnum):
    """Memory access levels for agents.

    Defines what memory layers an agent is allowed to access.
    """

    NONE = 0
    LAYER1_ONLY = 1
    LAYER1_AND_2 = 2
    LAYER1_2_AND_3_READ = 3
    LAYER1_2_3_AND_4_READ = 4
    FULL_ACCESS = 5


@dataclass
class AgentManifest:
    """Declaration of an agent's capabilities and access requirements.

    Attributes:
        name: Unique agent identifier.
        description: Human-readable description of the agent's role.
        required_tools: List of tool names this agent needs.
        memory_access_level: Maximum memory layer access.
        permission_level: Maximum permission level for operations.
        active_phase: The phase in which this agent becomes active.
    """

    name: str
    description: str
    required_tools: list[str] = field(default_factory=list)
    memory_access_level: MemoryAccessLevel = MemoryAccessLevel.NONE
    permission_level: PermissionLevel = PermissionLevel.READ_ONLY
    active_phase: int = 1


class BaseAgent(ABC):
    """Abstract base class for all Renine agents.

    All agents must:
    1. Declare a manifest via get_manifest().
    2. Implement process() to handle input and return a response.

    Agents communicate via LangGraph state, never by direct function
    calls between agent classes.
    """

    def __init__(self) -> None:
        """Initialize the base agent and log its manifest."""
        manifest = self.get_manifest()
        logger.info(
            "agent_initialized",
            agent=manifest.name,
            memory_access=manifest.memory_access_level.name,
            permission=manifest.permission_level.name,
            tools=manifest.required_tools,
        )

    @abstractmethod
    def get_manifest(self) -> AgentManifest:
        """Return the agent's capability manifest.

        Returns:
            AgentManifest declaring tools, memory access, and permissions.
        """

    @abstractmethod
    def process(
        self,
        user_input: str,
        context: list[dict[str, str]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process user input and return a response.

        Args:
            user_input: The user's text input.
            context: Optional conversation context (Layer 1 messages).
            metadata: Optional additional context from the router.

        Returns:
            Response dictionary with at least a "content" key.
        """

    def validate_memory_access(self, requested_layer: int) -> bool:
        """Check if this agent is allowed to access a memory layer.

        Args:
            requested_layer: Memory layer number (1-4).

        Returns:
            True if access is permitted.
        """
        manifest = self.get_manifest()
        access_map: dict[MemoryAccessLevel, set[int]] = {
            MemoryAccessLevel.NONE: set(),
            MemoryAccessLevel.LAYER1_ONLY: {1},
            MemoryAccessLevel.LAYER1_AND_2: {1, 2},
            MemoryAccessLevel.LAYER1_2_AND_3_READ: {1, 2, 3},
            MemoryAccessLevel.LAYER1_2_3_AND_4_READ: {1, 2, 3, 4},
            MemoryAccessLevel.FULL_ACCESS: {1, 2, 3, 4},
        }
        allowed = access_map.get(manifest.memory_access_level, set())
        return requested_layer in allowed

    def validate_permission(self, required_level: PermissionLevel) -> bool:
        """Check if this agent's permission level meets the requirement.

        Args:
            required_level: Minimum permission level required.

        Returns:
            True if the agent's permission level is sufficient.
        """
        manifest = self.get_manifest()
        return manifest.permission_level >= required_level
