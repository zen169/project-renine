"""Tests for renine.agents.base_agent — abstract base class."""
from __future__ import annotations

from typing import Any

import pytest

from renine.agents.base_agent import (
    AgentManifest,
    BaseAgent,
    MemoryAccessLevel,
)
from renine.tools.permissions import PermissionLevel


class _ConcreteAgent(BaseAgent):
    """Minimal concrete agent for testing."""

    def get_manifest(self) -> AgentManifest:
        return AgentManifest(
            name="test_agent",
            description="Test agent",
            memory_access_level=MemoryAccessLevel.LAYER1_AND_2,
            permission_level=PermissionLevel.STANDARD,
        )

    def process(
        self,
        user_input: str,
        context: list[dict[str, str]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {"content": f"echo: {user_input}", "success": True}


class TestAgentManifest:
    """Tests for AgentManifest dataclass."""

    def test_required_fields(self) -> None:
        """Manifest can be created with name and description."""
        m = AgentManifest(name="x", description="y")
        assert m.name == "x"
        assert m.description == "y"

    def test_default_tools_empty(self) -> None:
        """Default required_tools is empty list."""
        m = AgentManifest(name="x", description="y")
        assert m.required_tools == []

    def test_default_phase_one(self) -> None:
        """Default active_phase is 1."""
        m = AgentManifest(name="x", description="y")
        assert m.active_phase == 1


class TestBaseAgent:
    """Tests for BaseAgent via _ConcreteAgent."""

    def setup_method(self) -> None:
        self.agent = _ConcreteAgent()

    def test_get_manifest_returns_manifest(self) -> None:
        """get_manifest returns an AgentManifest."""
        assert isinstance(self.agent.get_manifest(), AgentManifest)

    def test_process_returns_dict(self) -> None:
        """process returns a dictionary with content key."""
        result = self.agent.process("Hello")
        assert isinstance(result, dict)
        assert "content" in result

    def test_validate_memory_access_allowed(self) -> None:
        """Layer within access level is permitted."""
        assert self.agent.validate_memory_access(1) is True
        assert self.agent.validate_memory_access(2) is True

    def test_validate_memory_access_denied(self) -> None:
        """Layer beyond access level is denied."""
        assert self.agent.validate_memory_access(3) is False

    def test_validate_permission_equal(self) -> None:
        """Agent's own permission level is sufficient."""
        assert self.agent.validate_permission(PermissionLevel.STANDARD) is True

    def test_validate_permission_lower(self) -> None:
        """Lower requirement passes."""
        assert self.agent.validate_permission(PermissionLevel.READ_ONLY) is True

    def test_validate_permission_higher_denied(self) -> None:
        """Higher requirement than agent's level fails."""
        assert self.agent.validate_permission(PermissionLevel.DESTRUCTIVE) is False

    def test_cannot_instantiate_abstract(self) -> None:
        """BaseAgent cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseAgent()  # type: ignore[abstract]
