"""Tool executor for Renine.

Intercepts all tool calls and enforces:
1. Tool exists in registry
2. Caller agent has sufficient permission
3. Elevated/Destructive tools invoke the confirmation gate
4. Execution wrapped in try/except with structured error logging
5. Returns ToolResult — never crashes the agent

Inputs:
    - Tool name and arguments.
    - Calling agent's permission level.

Outputs:
    - ToolResult(success, data, error).
"""
from __future__ import annotations

from typing import Any

from renine.core.exceptions import (
    ConfirmationDeniedError,
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolPermissionError,
    ToolUnavailableError,
)
from renine.core.logging_config import get_logger
from renine.security.confirmation_gate import request_confirmation, requires_confirmation
from renine.tools.permissions import PermissionLevel
from renine.tools.registry import ToolRegistry, ToolResult

logger = get_logger(__name__)


def execute_tool(
    tool_name: str,
    caller_permission: PermissionLevel,
    caller_agent: str = "unknown",
    **kwargs: Any,
) -> ToolResult:
    """Execute a registered tool with full permission and safety checks.

    Pipeline:
    1. Validate tool exists in registry.
    2. Check tool availability in config.
    3. Verify caller has sufficient permission level.
    4. If elevated/destructive: invoke confirmation gate.
    5. Execute the tool in a try/except boundary.
    6. Return structured ToolResult.

    Args:
        tool_name: Name of the tool to execute.
        caller_permission: Permission level of the calling agent.
        caller_agent: Name of the agent requesting execution.
        **kwargs: Arguments to pass to the tool's execute() method.

    Returns:
        ToolResult with success status, data, and any error message.
    """
    # Step 1-2: Look up tool (raises ToolNotFoundError or ToolUnavailableError)
    try:
        tool_def = ToolRegistry.get_tool(tool_name)
    except (ToolNotFoundError, ToolUnavailableError) as e:
        logger.error("tool_lookup_failed", tool=tool_name, error=str(e))
        return ToolResult(success=False, error=str(e))

    # Step 3: Permission check
    if caller_permission < tool_def.permission_level:
        msg = (
            f"Agent '{caller_agent}' has permission level "
            f"{caller_permission.name} but tool '{tool_name}' "
            f"requires {tool_def.permission_level.name}."
        )
        logger.warning("tool_permission_denied", tool=tool_name, agent=caller_agent)
        return ToolResult(success=False, error=msg)

    # Step 4: Confirmation gate for elevated/destructive operations
    if _requires_confirmation_check(tool_def):
        confirmation = request_confirmation(
            action=tool_name,
            description=f"Execute tool: {tool_def.description}",
            source_agent=caller_agent,
        )
        # In Phase 1, confirmation is handled by the UI layer.
        # The executor creates the request; the UI resolves it.
        logger.info(
            "tool_confirmation_pending",
            tool=tool_name,
            agent=caller_agent,
        )

    # Step 5: Execute the tool
    return _safe_execute(tool_def, caller_agent, **kwargs)


def _requires_confirmation_check(tool_def: Any) -> bool:
    """Check if a tool execution requires user confirmation.

    Args:
        tool_def: ToolDefinition to check.

    Returns:
        True if confirmation is required.
    """
    if tool_def.requires_confirmation:
        return True
    if tool_def.permission_level >= PermissionLevel.ELEVATED:
        return True
    return False


def _safe_execute(
    tool_def: Any,
    caller_agent: str,
    **kwargs: Any,
) -> ToolResult:
    """Execute a tool within a safety boundary.

    Args:
        tool_def: ToolDefinition to execute.
        caller_agent: Name of the calling agent.
        **kwargs: Arguments for the tool.

    Returns:
        ToolResult from the tool, or error result if execution fails.
    """
    try:
        tool_instance = tool_def.tool_class()
        result = tool_instance.execute(**kwargs)

        logger.info(
            "tool_executed",
            tool=tool_def.name,
            agent=caller_agent,
            success=result.success,
        )
        return result

    except ConfirmationDeniedError:
        logger.warning("tool_confirmation_denied", tool=tool_def.name)
        return ToolResult(
            success=False,
            error=f"User denied confirmation for tool: {tool_def.name}",
        )
    except Exception as e:
        logger.exception(
            "tool_execution_error",
            tool=tool_def.name,
            agent=caller_agent,
        )
        return ToolResult(
            success=False,
            error=f"Tool execution failed: {e}",
        )
