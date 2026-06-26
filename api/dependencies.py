"""Shared query helpers and sanitization utilities for Renine Mobile API.

All data returned by API endpoints is mediated through these helpers — no
endpoint accesses the database or memory layers directly.

Security rules enforced here:
  - Layer 1 (Context) messages are stripped of sensitive field names only.
  - Layer 2 (History) raw_turns field is always excluded from API responses.
  - Layer 3 (Mind) and Layer 4 (Personality) responses are filtered to ONLY
    the fields declared in security.yaml security.api.whitelisted_fields.
    The namespace check in sanitize() is intentionally bypassed here because
    we are NOT sending data to an external API — we are returning it to the
    authenticated local user.  Field-level stripping is still applied.
  - Smart device attributes are returned from the local cache as-is (no
    personal Layer 3/4 content stored in device attributes).
  - Pet medical_conditions and medications fields are intentionally excluded.
"""
from __future__ import annotations

import datetime
from typing import Any

from sqlalchemy import select

from renine.core.config import get_security_config
from renine.core.context_sanitizer import _load_sensitive_fields, _strip_sensitive_fields
from renine.core.logging_config import get_logger
from renine.databases.models.pending_smart_home_action import PendingSmartHomeAction
from renine.databases.models.pets import Pet
from renine.databases.models.smart_device import SmartDevice
from renine.databases.session import get_session
from renine.memory.expiration import get_scheduler
from renine.memory.memory_manager import MemoryManager

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers: whitelist + strip
# ---------------------------------------------------------------------------

def _get_mind_whitelist() -> set[str]:
    """Return the whitelisted field names for Layer 3 (Mind) API responses."""
    cfg = get_security_config()
    fields = (
        cfg.get("security", {})
        .get("api", {})
        .get("whitelisted_fields", {})
        .get("mind", [])
    )
    return set(fields)


def _get_personality_whitelist() -> set[str]:
    """Return the whitelisted field names for Layer 4 (Personality) API responses."""
    cfg = get_security_config()
    fields = (
        cfg.get("security", {})
        .get("api", {})
        .get("whitelisted_fields", {})
        .get("personality", [])
    )
    return set(fields)


def _apply_whitelist(record: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
    """Filter a record dictionary to only include whitelisted keys.

    Args:
        record: Source dictionary from a database or memory layer.
        allowed: Set of permitted field names.

    Returns:
        New dictionary containing only the allowed keys.
    """
    return {k: v for k, v in record.items() if k in allowed}


def _safe_strip(record: dict[str, Any]) -> dict[str, Any]:
    """Apply field-level sensitive-field stripping WITHOUT namespace check.

    Used for local-origin data going to the authenticated mobile user —
    we must not raise SanitizationError for local namespaces, but we still
    want to strip credential-like field names (password, token, secret, etc.).

    Args:
        record: Raw dictionary.

    Returns:
        Record with sensitive field names replaced by [REDACTED].
    """
    sensitive_fields = _load_sensitive_fields()
    return _strip_sensitive_fields(record, sensitive_fields)


# ---------------------------------------------------------------------------
# Memory — Layer 1 (Context)
# ---------------------------------------------------------------------------

def get_layer1_context() -> list[dict[str, Any]]:
    """Retrieve the current in-memory conversation context (Layer 1).

    Returns:
        List of message dicts with 'role' and 'content' keys.
    """
    mm = MemoryManager()
    messages = mm.get_messages()
    # Strip any accidentally included credential-like field names
    return [_safe_strip(m) for m in messages]


# ---------------------------------------------------------------------------
# Memory — Layer 2 (History)
# ---------------------------------------------------------------------------

def get_layer2_history(limit: int = 20) -> list[dict[str, Any]]:
    """Retrieve recent conversation history from Layer 2 (SQLite).

    Args:
        limit: Maximum number of conversations to return.

    Returns:
        List of conversation summary dicts WITHOUT raw_turns.
    """
    mm = MemoryManager()
    conversations = mm.get_recent_conversations(limit=limit)
    result = []
    for c in conversations:
        # raw_turns is always excluded — may contain sensitive personal data
        safe: dict[str, Any] = {
            "id": c.get("id"),
            "date": c.get("date"),
            "summary": c.get("summary", ""),
            "created_at": c.get("created_at", ""),
        }
        result.append(safe)
    return result


# ---------------------------------------------------------------------------
# Memory — Layer 3 (Mind)
# ---------------------------------------------------------------------------

def get_layer3_mind(
    namespace: str,
    query: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Retrieve facts from Layer 3 (Mind database), filtered by whitelist.

    Namespace is required — enumerating all namespaces is disallowed for
    privacy reasons.  Field-level sanitization is applied, then the
    security.api.whitelisted_fields.mind allow-list is enforced.

    Args:
        namespace: Required namespace filter (e.g. 'house', 'calendar_events').
        query: Optional semantic search query.
        limit: Maximum number of records to return.

    Returns:
        List of whitelisted fact dicts.
    """
    from renine.databases.models.mind import MindRecord
    whitelist = _get_mind_whitelist()

    db = get_session("mind_db")
    try:
        if query:
            mm = MemoryManager()
            search_results = mm.search_facts(namespace, query, limit=limit)
            keys = [res["key"] for res in search_results if "key" in res]
            if not keys:
                return []
            stmt = select(MindRecord).where(
                MindRecord.namespace == namespace,
                MindRecord.key.in_(keys)
            )
            records_map = {r.key: r for r in db.scalars(stmt).all()}
            records = [records_map[k] for k in keys if k in records_map]
        else:
            stmt = select(MindRecord).where(MindRecord.namespace == namespace).limit(limit)
            records = list(db.scalars(stmt).all())

        result: list[dict[str, Any]] = []
        for r in records:
            r_dict = {
                "id": r.id,
                "namespace": r.namespace,
                "key": r.key,
                "summary": r.summary,
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "updated_at": r.updated_at.isoformat() if r.updated_at else "",
                "value": r.value,
            }
            stripped = _safe_strip(r_dict)
            whitelisted = _apply_whitelist(stripped, whitelist)
            result.append(whitelisted)

        return result
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Memory — Layer 4 (Personality)
# ---------------------------------------------------------------------------

def get_layer4_personality(
    query: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Retrieve people profiles from Layer 4, filtered by whitelist.

    Field-level sanitization is applied first, then the
    security.api.whitelisted_fields.personality allow-list is enforced.
    Deep personal data (notes, food_preferences, hobbies, etc.) is excluded.

    Args:
        query: Optional semantic search query.
        limit: Maximum number of records to return.

    Returns:
        List of whitelisted person dicts.
    """
    from renine.databases.models.personality import Person
    whitelist = _get_personality_whitelist()

    db = get_session("personality_db")
    try:
        if query:
            mm = MemoryManager()
            search_results = mm.search_people(query, limit=limit)
            names = [res["name"] for res in search_results if "name" in res]
            if not names:
                return []
            stmt = select(Person).where(Person.name.in_(names))
            records_map = {r.name: r for r in db.scalars(stmt).all()}
            records = [records_map[n] for n in names if n in records_map]
        else:
            stmt = select(Person).limit(limit)
            records = list(db.scalars(stmt).all())

        result: list[dict[str, Any]] = []
        for r in records:
            r_dict = {
                "name": r.name,
                "relationship": r.relationship,
                "age": r.age,
                "birthday": r.birthday,
                "food_preferences": r.food_preferences,
                "hobbies": r.hobbies,
                "personality_traits": r.personality_traits,
                "goals": r.goals,
                "habits": r.habits,
                "notes": r.notes,
                "updated_at": r.updated_at.isoformat() if r.updated_at else "",
            }
            stripped = _safe_strip(r_dict)
            whitelisted = _apply_whitelist(stripped, whitelist)
            result.append(whitelisted)

        return result
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Smart Home — Devices
# ---------------------------------------------------------------------------

def get_smart_devices(domain: str | None = None) -> list[dict[str, Any]]:
    """Retrieve cached smart home devices from the local database.

    Args:
        domain: Optional HA domain filter (e.g. 'light').

    Returns:
        List of device dicts (no personal Layer 3/4 data).
    """
    db = get_session("mind_db")
    try:
        stmt = select(SmartDevice)
        if domain:
            stmt = stmt.where(SmartDevice.domain == domain)
        devices = list(db.scalars(stmt).all())
        return [
            {
                "id": d.id,
                "entity_id": d.entity_id,
                "name": d.name,
                "domain": d.domain,
                "state": d.state,
                "last_synced": d.last_synced.isoformat() if d.last_synced else None,
                "updated_at": d.updated_at.isoformat(),
            }
            for d in devices
        ]
    finally:
        db.close()


def get_smart_device_by_entity(entity_id: str) -> dict[str, Any] | None:
    """Retrieve a single cached device by entity_id.

    Args:
        entity_id: Home Assistant entity ID.

    Returns:
        Device dict including attributes, or None if not found.
    """
    db = get_session("mind_db")
    try:
        device = db.scalar(
            select(SmartDevice).where(SmartDevice.entity_id == entity_id)
        )
        if device is None:
            return None
        return {
            "entity_id": device.entity_id,
            "name": device.name,
            "domain": device.domain,
            "state": device.state,
            "attributes": device.attributes or {},
            "last_synced": device.last_synced.isoformat() if device.last_synced else None,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Smart Home — Pending Actions
# ---------------------------------------------------------------------------

def create_pending_action(
    entity_id: str,
    domain: str,
    service: str,
    ttl_seconds: int = 300,
) -> dict[str, Any]:
    """Insert a new PendingSmartHomeAction and cancel any existing ones.

    Args:
        entity_id: Home Assistant entity ID.
        domain: HA domain (must be in ALLOWED_DOMAINS).
        service: HA service name (must be in ALLOWED_SERVICES).
        ttl_seconds: Seconds until this confirmation expires.

    Returns:
        Dict representation of the created action.

    Raises:
        ValueError: If entity_id format, domain, or service is invalid.
    """
    from renine.tools.smart_home.hass_client import (
        ALLOWED_DOMAINS,
        ALLOWED_SERVICES,
        validate_entity_id,
    )

    validate_entity_id(entity_id)
    if domain not in ALLOWED_DOMAINS:
        raise ValueError(f"Domain '{domain}' is not permitted.")
    if service not in ALLOWED_SERVICES:
        raise ValueError(f"Service '{service}' is not permitted.")

    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = now + datetime.timedelta(seconds=ttl_seconds)

    db = get_session("mind_db")
    try:
        # Cancel any previously pending action
        existing = list(
            db.scalars(
                select(PendingSmartHomeAction).where(
                    PendingSmartHomeAction.status == "pending"
                )
            ).all()
        )
        for row in existing:
            row.status = "cancelled"

        action = PendingSmartHomeAction(
            entity_id=entity_id,
            domain=domain,
            service=service,
            service_data={},
            requested_at=now,
            expires_at=expires_at,
            status="pending",
        )
        db.add(action)
        db.commit()
        db.refresh(action)

        return {
            "id": action.id,
            "entity_id": action.entity_id,
            "domain": action.domain,
            "service": action.service,
            "status": action.status,
            "requested_at": action.requested_at.isoformat(),
            "expires_at": action.expires_at.isoformat(),
        }
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def confirm_pending_action(action_id: int) -> dict[str, Any]:
    """Execute a pending smart home action after mobile-user confirmation.

    Loads the PendingSmartHomeAction by ID, validates it is still pending
    and not expired, then calls HassClient.call_service(). Marks the action
    as 'executed' on success or 'cancelled' on failure.

    Args:
        action_id: Primary key of the PendingSmartHomeAction to execute.

    Returns:
        Dict with success, message, entity_id, and service keys.

    Raises:
        ValueError: If action is not found, not pending, or expired.
    """
    from renine.tools.smart_home.hass_client import HassClient, HassError

    # Read action details first
    db = get_session("mind_db")
    try:
        action = db.scalar(
            select(PendingSmartHomeAction).where(
                PendingSmartHomeAction.id == action_id
            )
        )
        if action is None:
            raise ValueError(f"Action #{action_id} not found.")
        if action.status != "pending":
            raise ValueError(f"Action #{action_id} is not pending (status={action.status!r}).")
        if action.is_expired():
            action.status = "expired"
            db.commit()
            raise ValueError(f"Action #{action_id} has expired.")

        entity_id = action.entity_id
        domain = action.domain
        service = action.service
        service_data = action.service_data or {}
    finally:
        db.close()

    # Execute via HassClient (separate scope from DB transaction)
    try:
        with HassClient() as client:
            client.call_service(domain, service, entity_id, service_data or None)
    except HassError as exc:
        _update_action_status(action_id, "cancelled")
        raise ValueError(f"HassClient error: {exc}") from exc

    _update_action_status(action_id, "executed")
    return {
        "success": True,
        "message": f"{service.replace('_', ' ')} executed on {entity_id}.",
        "entity_id": entity_id,
        "service": service,
    }


def _update_action_status(action_id: int, status: str) -> None:
    """Update the status field of a PendingSmartHomeAction by ID.

    Args:
        action_id: Primary key.
        status: New status value ('executed', 'expired', 'cancelled').
    """
    db = get_session("mind_db")
    try:
        action = db.get(PendingSmartHomeAction, action_id)
        if action is not None:
            action.status = status
            db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Pets
# ---------------------------------------------------------------------------

def get_pets() -> list[dict[str, Any]]:
    """Retrieve all pet profiles from the database.

    Intentionally excludes medical_conditions and medications (sensitive
    health data that must not leave the local system).

    Returns:
        List of safe pet dicts.
    """
    db = get_session("mind_db")
    try:
        pets = list(db.scalars(select(Pet)).all())
        return [
            {
                "id": p.id,
                "name": p.name,
                "species": p.species,
                "breed": p.breed,
                "age": p.age,
                "feeding_schedule": p.feeding_schedule,
                "last_fed": p.last_fed.isoformat() if p.last_fed else None,
                "updated_at": p.updated_at.isoformat(),
            }
            for p in pets
        ]
    finally:
        db.close()


def feed_pet(name: str) -> bool:
    """Record a feeding event for the named pet.

    Args:
        name: Name of the pet.

    Returns:
        True if the pet was found and updated, False otherwise.
    """
    db = get_session("mind_db")
    try:
        pet = db.scalar(select(Pet).where(Pet.name == name))
        if pet is None:
            return False
        pet.last_fed = datetime.datetime.now(datetime.timezone.utc)
        db.commit()
        logger.info("api_pet_fed", pet_name=name)
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Reminders
# ---------------------------------------------------------------------------

def get_scheduled_reminders() -> list[dict[str, Any]]:
    """Retrieve all active APScheduler jobs as reminder entries.

    Returns:
        List of job dicts with id, name, and next_run_time. Returns empty
        list if the scheduler is not running.
    """
    try:
        scheduler = get_scheduler()
        jobs = scheduler.get_jobs()
        return [
            {
                "id": job.id,
                "name": getattr(job, "name", None),
                "next_run_time": (
                    job.next_run_time.isoformat()
                    if getattr(job, "next_run_time", None)
                    else None
                ),
            }
            for job in jobs
        ]
    except Exception as exc:
        logger.warning("get_scheduled_reminders_failed", error=str(exc))
        return []
