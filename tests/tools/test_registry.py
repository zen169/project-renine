"""Tests for renine.tools.registry — tool registration and discovery."""
from __future__ import annotations

import pytest

from renine.core.exceptions import ToolNotFoundError
from renine.tools.permissions import PermissionLevel
from renine.tools.registry import BaseTool, ToolRegistry, ToolResult, register_tool


@register_tool(
    name="_test_tool_abc",
    description="Temporary test tool",
    permission_level=PermissionLevel.READ_ONLY,
)
class _TestTool(BaseTool):
    """Test tool that always succeeds."""

    def execute(self, **kwargs: object) -> ToolResult:
        """Return a success result."""
        return ToolResult(success=True, data="ok")


class TestToolRegistry:
    """Tests for ToolRegistry."""

    def test_registered_tool_listed(self) -> None:
        """Tool registered via decorator appears in list_tools."""
        names = [t.name for t in ToolRegistry.list_tools()]
        assert "_test_tool_abc" in names

    def test_unregistered_tool_raises(self) -> None:
        """Requesting unknown tool raises ToolNotFoundError."""
        with pytest.raises(ToolNotFoundError):
            ToolRegistry.get_tool("__nonexistent_tool__")

    def test_clear_empties_registry(self) -> None:
        """clear() removes all registered tools."""
        ToolRegistry.clear()
        assert ToolRegistry.list_tools() == []

    def test_register_directly(self) -> None:
        """Tools can be re-registered after clear."""
        ToolRegistry.clear()
        register_tool(
            name="_test_tool_abc",
            description="Re-registered",
            permission_level=PermissionLevel.READ_ONLY,
        )(_TestTool)
        names = [t.name for t in ToolRegistry.list_tools()]
        assert "_test_tool_abc" in names


class TestBaseTool:
    """Tests for BaseTool."""

    def test_cannot_instantiate_abstract(self) -> None:
        """BaseTool cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseTool()  # type: ignore[abstract]

    def test_concrete_tool_executes(self) -> None:
        """Concrete tool returns ToolResult."""
        tool = _TestTool()
        result = tool.execute()
        assert result.success is True
        assert result.data == "ok"


class TestToolResult:
    """Tests for ToolResult dataclass."""

    def test_success_result(self) -> None:
        """Success result has correct attributes."""
        r = ToolResult(success=True, data=42)
        assert r.success is True
        assert r.data == 42
        assert r.error is None

    def test_error_result(self) -> None:
        """Error result has error message."""
        r = ToolResult(success=False, error="failed")
        assert r.success is False
        assert r.error == "failed"
