"""Permission levels for the Renine tool system.

Defines the permission hierarchy used by tool registration,
agent manifests, and the tool executor's permission checks.

This module is the single source of truth for permission levels
across the entire tool system.
"""
from __future__ import annotations

from enum import IntEnum


class PermissionLevel(IntEnum):
    """Permission levels for tool operations.

    Each level implies all permissions of lower levels.

    Attributes:
        READ_ONLY: Safe reads with no side effects.
        STANDARD: Normal actions that are reversible.
        ELEVATED: Requires user confirmation before execution.
        DESTRUCTIVE: Hard confirmation + audit log required.
    """

    READ_ONLY = 0
    STANDARD = 1
    ELEVATED = 2
    DESTRUCTIVE = 3
