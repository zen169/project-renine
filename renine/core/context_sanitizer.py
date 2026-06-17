"""Context sanitizer for Renine.

Strips sensitive data from payloads before they are sent to any external
API (e.g., Anthropic Claude fallback). This module enforces the absolute
rule that Layer 3 (Mind) and Layer 4 (Personality) data NEVER leaves
the local system.

The sanitizer operates in two modes:
1. Field-level stripping: Removes known sensitive field names from dicts.
2. Namespace blocking: Rejects entire payloads originating from local-only
   namespaces.

Inputs:
    - Payload dictionary to sanitize.
    - config/security.yaml for sensitive field definitions.

Outputs:
    - Sanitized payload safe for external transmission.

Raises:
    SanitizationError: If a local-only namespace is detected in the payload.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from renine.core.config import get_security_config
from renine.core.exceptions import SanitizationError
from renine.core.logging_config import get_logger

logger = get_logger(__name__)

# Sentinel value used to replace stripped fields
_REDACTED = "[REDACTED]"


def _load_sensitive_fields() -> set[str]:
    """Load the set of sensitive field names from security config.

    Returns:
        Set of lowercase field name strings to strip.
    """
    config = get_security_config()
    sanitizer_config = config.get("security", {}).get("sanitizer", {})
    fields = sanitizer_config.get("sensitive_fields", [])
    return {f.lower() for f in fields}


def _load_local_only_namespaces() -> set[str]:
    """Load the set of local-only namespaces from security config.

    Returns:
        Set of namespace strings that must never be sent externally.
    """
    config = get_security_config()
    sanitizer_config = config.get("security", {}).get("sanitizer", {})
    namespaces = sanitizer_config.get("local_only_namespaces", [])
    return {ns.lower() for ns in namespaces}


def _strip_sensitive_fields(
    data: dict[str, Any],
    sensitive_fields: set[str],
) -> dict[str, Any]:
    """Recursively strip sensitive fields from a dictionary.

    Args:
        data: Dictionary to sanitize.
        sensitive_fields: Set of lowercase field names to strip.

    Returns:
        New dictionary with sensitive fields replaced by _REDACTED.
    """
    sanitized: dict[str, Any] = {}

    for key, value in data.items():
        if key.lower() in sensitive_fields:
            sanitized[key] = _REDACTED
            logger.debug("field_redacted", field=key)
        elif isinstance(value, dict):
            sanitized[key] = _strip_sensitive_fields(value, sensitive_fields)
        elif isinstance(value, list):
            sanitized[key] = [
                _strip_sensitive_fields(item, sensitive_fields)
                if isinstance(item, dict)
                else item
                for item in value
            ]
        else:
            sanitized[key] = value

    return sanitized


def check_namespace(namespace: str) -> None:
    """Verify that a namespace is allowed for external transmission.

    Args:
        namespace: Namespace identifier to check.

    Raises:
        SanitizationError: If the namespace is classified as local-only.
    """
    local_only = _load_local_only_namespaces()
    if namespace.lower() in local_only:
        msg = (
            f"Namespace '{namespace}' is classified LOCAL ONLY. "
            f"Data from this namespace must NEVER be sent to external APIs."
        )
        logger.error("namespace_blocked", namespace=namespace)
        raise SanitizationError(msg)


def sanitize(payload: dict[str, Any]) -> dict[str, Any]:
    """Sanitize a payload for external API transmission.

    Performs deep copy then strips all sensitive fields. If a
    'namespace' key is present, validates it is not local-only.

    Args:
        payload: Raw payload dictionary.

    Returns:
        Deep-copied, sanitized payload safe for external use.

    Raises:
        SanitizationError: If the payload contains a local-only namespace.
    """
    # Check namespace if present
    namespace = payload.get("namespace", payload.get("source_namespace", ""))
    if namespace:
        check_namespace(str(namespace))

    # Deep copy to avoid mutating the original
    sanitized = deepcopy(payload)

    # Strip sensitive fields
    sensitive_fields = _load_sensitive_fields()
    sanitized = _strip_sensitive_fields(sanitized, sensitive_fields)

    logger.info("payload_sanitized", original_keys=list(payload.keys()))
    return sanitized
