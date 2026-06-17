"""Tool registry for Renine.

Provides a decorator-based registration system for tools and a
centralized registry for tool discovery. Tools are registered at
import time and can be queried by name, permission level, or
availability.

Usage:
    @register_tool(
        name="set_alarm",
        description="Set an alarm for a specific time",
        permission_level=PermissionLevel.STANDARD,
        requires_confirmation=False,
    )
    class SetAlarmTool(BaseTool):
        def execute(self, **kwargs) -> ToolResult: ...

Inputs:
    - Tool class decorated with @register_tool.
    - config/tools.yaml for availability flags.

Outputs:
    - Registered tools accessible via ToolRegistry.get_tool().
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, TypeVar

from renine.core.config import get_tools_config
from renine.core.exceptions import ToolNotFoundError, ToolUnavailableError
from renine.core.logging_config import get_logger
from renine.tools.permissions import PermissionLevel

logger = get_logger(__name__)

T = TypeVar("T", bound="BaseTool")


@dataclass
class ToolResult:
    """Result of a tool execution.

    Attributes:
        success: Whether the tool executed successfully.
        data: Result data from the tool (if successful).
        error: Error message (if failed).
        metadata: Additional result context.
    """

    success: bool
    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolDefinition:
    """Metadata about a registered tool.

    Attributes:
        name: Unique tool identifier.
        description: Human-readable description.
        permission_level: Required permission level.
        requires_confirmation: Whether user confirmation is needed.
        tool_class: The actual tool class.
    """

    name: str
    description: str
    permission_level: PermissionLevel
    requires_confirmation: bool
    tool_class: type[BaseTool]


class BaseTool(ABC):
    """Abstract base class for all Renine tools.

    All tools must implement the execute() method, which performs
    the tool's action and returns a ToolResult.
    """

    @abstractmethod
    def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool's action.

        Args:
            **kwargs: Tool-specific arguments.

        Returns:
            ToolResult indicating success or failure.
        """


class ToolRegistry:
    """Centralized registry for all Renine tools.

    Tools register themselves via the @register_tool decorator.
    The registry provides lookup by name and availability checking
    against config/tools.yaml.
    """

    _tools: dict[str, ToolDefinition] = {}

    @classmethod
    def register(cls, definition: ToolDefinition) -> None:
        """Register a tool in the registry.

        Args:
            definition: ToolDefinition with metadata and class reference.
        """
        cls._tools[definition.name] = definition
        logger.info(
            "tool_registered",
            name=definition.name,
            permission=definition.permission_level.name,
        )

    @classmethod
    def get_tool(cls, name: str) -> ToolDefinition:
        """Look up a tool by name.

        Args:
            name: Tool identifier.

        Returns:
            ToolDefinition for the requested tool.

        Raises:
            ToolNotFoundError: If no tool with this name is registered.
            ToolUnavailableError: If the tool is disabled in config.
        """
        if name not in cls._tools:
            raise ToolNotFoundError(f"Tool '{name}' is not registered.")

        if not cls.is_available(name):
            raise ToolUnavailableError(f"Tool '{name}' is disabled in config.")

        return cls._tools[name]

    @classmethod
    def is_available(cls, name: str) -> bool:
        """Check if a tool is enabled in the tools configuration.

        Args:
            name: Tool identifier.

        Returns:
            True if the tool is enabled.
        """
        try:
            config = get_tools_config()
            tools_config = config.get("tools", {})
            tool_config = tools_config.get(name, {})
            return bool(tool_config.get("enabled", False))
        except Exception:
            return False

    @classmethod
    def list_tools(cls) -> list[ToolDefinition]:
        """List all registered tools.

        Returns:
            List of all ToolDefinitions in the registry.
        """
        return list(cls._tools.values())

    @classmethod
    def list_available_tools(cls) -> list[ToolDefinition]:
        """List only tools that are enabled in config.

        Returns:
            List of enabled ToolDefinitions.
        """
        return [t for t in cls._tools.values() if cls.is_available(t.name)]

    @classmethod
    def clear(cls) -> None:
        """Clear all registered tools. Used in testing."""
        cls._tools.clear()


def register_tool(
    name: str,
    description: str,
    permission_level: PermissionLevel = PermissionLevel.STANDARD,
    requires_confirmation: bool = False,
) -> Any:
    """Decorator to register a tool class in the global registry.

    Args:
        name: Unique tool identifier.
        description: Human-readable tool description.
        permission_level: Required permission level.
        requires_confirmation: Whether confirmation is needed.

    Returns:
        Decorator function that registers the tool class.
    """
    def decorator(cls: type[BaseTool]) -> type[BaseTool]:
        definition = ToolDefinition(
            name=name,
            description=description,
            permission_level=permission_level,
            requires_confirmation=requires_confirmation,
            tool_class=cls,
        )
        ToolRegistry.register(definition)
        return cls

    return decorator
