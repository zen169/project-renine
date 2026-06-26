"""Smart Home agent for Phase 7 (7A read-only + 7B controlled device actions).

Phase 7A: Entity discovery, state queries, and cache synchronisation.
    - GET-only; no POST, PUT, PATCH, DELETE, no service calls.
    - HassClient is the sole component allowed to make HTTP requests.

Phase 7B: Safe device control via a mandatory confirmation gate.
    - Allowlisted domains: light, switch, fan, cover.
    - Allowlisted services: turn_on, turn_off, toggle, open_cover, close_cover, stop_cover.
    - Every state-changing action is stored as a PendingSmartHomeAction in the DB.
    - Action is executed only after explicit user confirmation.
    - Pending actions expire after 5 minutes.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select

from renine.agents.base_agent import AgentManifest, BaseAgent, MemoryAccessLevel
from renine.core.config import get_settings
from renine.core.logging_config import get_logger
from renine.databases.models.pending_smart_home_action import PendingSmartHomeAction
from renine.databases.models.smart_device import SmartDevice
from renine.databases.session import get_session
from renine.tools.permissions import PermissionLevel
from renine.tools.smart_home.hass_client import (
    ALLOWED_DOMAINS,
    ALLOWED_SERVICES,
    HassAuthError,
    HassClient,
    HassConnectionError,
    HassResponseError,
    HassServiceError,
    validate_entity_id,
)

logger = get_logger(__name__)

# Default TTL for pending confirmation actions (seconds)
_DEFAULT_CONFIRMATION_TTL = 300

# Natural-language → HA service mapping
_SERVICE_MAP: dict[str, str] = {
    "turn on": "turn_on",
    "turn_on": "turn_on",
    "switch on": "turn_on",
    "turn off": "turn_off",
    "turn_off": "turn_off",
    "switch off": "turn_off",
    "toggle": "toggle",
    "open": "open_cover",
    "open cover": "open_cover",
    "close": "close_cover",
    "close cover": "close_cover",
    "stop": "stop_cover",
    "stop cover": "stop_cover",
}

# Confirmation keywords that execute a pending action
_CONFIRMATION_KEYWORDS = frozenset({"yes", "y", "confirm", "ok", "do it"})


class SmartHomeAgent(BaseAgent):
    """Smart home agent: read-only discovery (Phase 7A) + safe device control (Phase 7B).

    All HTTP requests are delegated to HassClient. No httpx, requests, or
    socket usage exists in this class. Database writes are limited to
    idempotent upserts into smart_devices and lifecycle management of
    pending_smart_home_actions.
    """

    def __init__(self) -> None:
        """Initialise the SmartHomeAgent."""
        super().__init__()

    def get_manifest(self) -> AgentManifest:
        """Return the capability manifest for SmartHomeAgent."""
        return AgentManifest(
            name="smart_home",
            description=(
                "Smart home agent. Discovers and caches Home Assistant entity states "
                "(Phase 7A) and executes allowlisted device control actions after "
                "mandatory user confirmation (Phase 7B)."
            ),
            required_tools=[],
            memory_access_level=MemoryAccessLevel.LAYER1_AND_2,
            permission_level=PermissionLevel.STANDARD,
            active_phase=7,
        )

    # ------------------------------------------------------------------
    # Public interface: process()
    # ------------------------------------------------------------------

    def process(
        self,
        user_input: str,
        context: list[dict[str, str]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Dispatch user input to the appropriate operation.

        Routing order (case-insensitive):
          1. Confirmation reply           → execute_confirmed_action()
          2. Control intent               → request_confirmation()
          3. "sync" | "discover" | "refresh" → sync_devices()
          4. "status" | "state" + entity   → get_device_status(entity_id)
          5. "list" | "show" | "devices"  → list_cached_devices()
          6. "connection" | "ping"         → check_connection()
          7. default                       → help message

        Args:
            user_input: Natural language query from the user.
            context: Optional conversation context (ignored by this agent).
            metadata: Optional router metadata (ignored by this agent).

        Returns:
            Response dictionary with at least "content" and "success" keys.
        """
        settings = get_settings()
        if not settings.get("features", {}).get("smart_home_enabled", False):
            return {
                "content": (
                    "Smart home integration is currently disabled. "
                    "Set features.smart_home_enabled to true in settings.yaml to enable it."
                ),
                "success": False,
                "source_agent": "smart_home",
            }

        query = user_input.lower().strip()

        # Phase 7B: Check for confirmation of a pending action first
        if self._is_confirmation(query):
            return self._execute_confirmed_action()

        # Phase 7B: Detect control intent (turn on/off/toggle/open/close/stop)
        control_intent = self._detect_control_intent(query)
        if control_intent is not None:
            service, entity_id = control_intent
            domain = entity_id.split(".")[0]
            return self._request_confirmation(entity_id, domain, service)

        # Phase 7A: Read-only routing
        # Route: sync / discover / refresh
        if any(kw in query for kw in ("sync", "discover", "refresh")):
            return self.sync_devices()

        # Route: status / state — extract entity_id token after the keyword
        if any(kw in query for kw in ("status", "state")):
            tokens = user_input.strip().split()
            entity_id = next((t for t in tokens if "." in t), None)
            if entity_id is None:
                return {
                    "content": (
                        "Please provide an entity ID, e.g. "
                        "'status light.living_room'."
                    ),
                    "success": False,
                    "source_agent": "smart_home",
                }
            return self.get_device_status(entity_id)

        # Route: list / show / devices
        if any(kw in query for kw in ("list", "show", "devices")):
            domain = None
            known_domains = ("light", "switch", "sensor", "binary_sensor", "climate",
                             "cover", "fan", "media_player", "lock", "camera")
            for dom in known_domains:
                if dom in query:
                    domain = dom
                    break
            return self.list_cached_devices(domain=domain)

        # Route: connection / ping
        if any(kw in query for kw in ("connection", "ping", "connect")):
            return self.check_connection()

        # Default: help text
        return {
            "content": (
                "I can help you with smart home control. Try:\n"
                "  • 'sync devices' — fetch and cache all entities from Home Assistant\n"
                "  • 'status light.living_room' — get the current state of an entity\n"
                "  • 'list devices' — show all cached entities\n"
                "  • 'connection' — verify Home Assistant connectivity\n"
                "  • 'turn on light.living_room' — turn on a device (requires confirmation)\n"
                "  • 'turn off switch.kitchen' — turn off a device (requires confirmation)\n"
                "  • 'toggle fan.bedroom' — toggle a device (requires confirmation)"
            ),
            "success": True,
            "source_agent": "smart_home",
        }

    # ------------------------------------------------------------------
    # Phase 7A: Read-only operations
    # ------------------------------------------------------------------

    def sync_devices(self) -> dict[str, Any]:
        """Discover all Home Assistant entities and upsert them into the cache.

        Calls GET /api/states via HassClient. Each entity is processed
        individually: malformed entities are skipped without aborting the
        remaining batch. A single commit is issued after the loop.

        Returns:
            Dict with "synced" (int), "errors" (int), "content" (str),
            "success" (bool), and "source_agent" (str).
        """
        try:
            with HassClient() as client:
                entities = client.discover_entities()
        except HassAuthError as e:
            logger.warning("sync_devices: authentication error", exc_type=type(e).__name__)
            return {
                "content": "Home Assistant authentication failed. Check your access token.",
                "success": False,
                "synced": 0,
                "errors": 0,
                "source_agent": "smart_home",
            }
        except (HassConnectionError, HassResponseError) as e:
            logger.warning(
                "sync_devices: retrieval error",
                exc_type=type(e).__name__,
            )
            return {
                "content": f"Failed to retrieve entities from Home Assistant: {type(e).__name__}",
                "success": False,
                "synced": 0,
                "errors": 0,
                "source_agent": "smart_home",
            }

        synced = 0
        errors = 0
        db = get_session("mind_db")
        try:
            for raw in entities:
                try:
                    self._upsert_device(db, raw)
                    synced += 1
                except (ValueError, KeyError, TypeError) as e:
                    # Malformed entity: log and continue with remaining entities
                    logger.debug(
                        "sync_devices: skipping malformed entity",
                        exc_type=type(e).__name__,
                        operation="upsert",
                    )
                    errors += 1
                    continue

            # Single commit after the full loop
            db.commit()
            logger.info(
                "sync_devices: complete",
                operation="sync",
                synced=synced,
                errors=errors,
            )
        except Exception:
            db.rollback()
            logger.exception("sync_devices: unexpected DB error, rolled back")
            return {
                "content": "An unexpected database error occurred during sync. Changes were rolled back.",
                "success": False,
                "synced": 0,
                "errors": errors,
                "source_agent": "smart_home",
            }
        finally:
            db.close()

        return {
            "content": (
                f"Sync complete. {synced} device(s) updated in cache."
                + (f" {errors} entity/entities skipped due to malformed data." if errors else "")
            ),
            "success": True,
            "synced": synced,
            "errors": errors,
            "source_agent": "smart_home",
        }

    def get_device_status(self, entity_id: str) -> dict[str, Any]:
        """Retrieve the current state of a single entity from Home Assistant.

        Validates the entity_id format before making any network call.
        Returns None gracefully on 404 (entity not found in HASS).

        Args:
            entity_id: Home Assistant entity ID (e.g. 'light.living_room').

        Returns:
            Dict with "content" (str), "success" (bool), "entity_id" (str),
            "state" (str | None), "attributes" (dict | None), "source_agent" (str).
        """
        try:
            validate_entity_id(entity_id)
        except ValueError as e:
            return {
                "content": f"Invalid entity ID: {e}",
                "success": False,
                "entity_id": entity_id,
                "state": None,
                "attributes": None,
                "source_agent": "smart_home",
            }

        try:
            with HassClient() as client:
                state = client.get_entity_state(entity_id)
        except HassAuthError as e:
            logger.warning(
                "get_device_status: authentication error",
                entity_id=entity_id,
                exc_type=type(e).__name__,
            )
            return {
                "content": "Home Assistant authentication failed. Check your access token.",
                "success": False,
                "entity_id": entity_id,
                "state": None,
                "attributes": None,
                "source_agent": "smart_home",
            }
        except (HassConnectionError, HassResponseError) as e:
            logger.warning(
                "get_device_status: retrieval error",
                entity_id=entity_id,
                exc_type=type(e).__name__,
            )
            return {
                "content": f"Failed to retrieve state for '{entity_id}': {type(e).__name__}",
                "success": False,
                "entity_id": entity_id,
                "state": None,
                "attributes": None,
                "source_agent": "smart_home",
            }

        if state is None:
            logger.debug(
                "get_device_status: entity not found",
                entity_id=entity_id,
                operation="get_state",
            )
            return {
                "content": f"Entity '{entity_id}' was not found in Home Assistant.",
                "success": True,
                "entity_id": entity_id,
                "state": None,
                "attributes": None,
                "source_agent": "smart_home",
            }

        current_state = state.get("state", "unknown")
        attributes = state.get("attributes", {})
        friendly = attributes.get("friendly_name", entity_id)

        logger.debug(
            "get_device_status: success",
            entity_id=entity_id,
            operation="get_state",
        )
        return {
            "content": f"{friendly} is currently '{current_state}'.",
            "success": True,
            "entity_id": entity_id,
            "state": current_state,
            "attributes": attributes,
            "source_agent": "smart_home",
        }

    def list_cached_devices(
        self,
        domain: str | None = None,
    ) -> dict[str, Any]:
        """List all locally cached smart devices, optionally filtered by domain.

        Pure database read — no network call is made.

        Args:
            domain: Optional HA domain filter (e.g. 'light', 'switch').

        Returns:
            Dict with "content" (str), "success" (bool), "devices" (list[dict]),
            "source_agent" (str).
        """
        db = get_session("mind_db")
        try:
            stmt = select(SmartDevice)
            if domain:
                stmt = stmt.where(SmartDevice.domain == domain)
            devices = list(db.scalars(stmt).all())
        finally:
            db.close()

        if not devices:
            label = f" in domain '{domain}'" if domain else ""
            return {
                "content": f"No devices{label} found in the local cache.",
                "success": True,
                "devices": [],
                "source_agent": "smart_home",
            }

        lines = [
            f"- {d.entity_id} ({d.domain}) — {d.state}"
            + (f" [{d.name}]" if d.name and d.name != d.entity_id else "")
            for d in devices
        ]
        header = f"Cached smart devices{f' (domain: {domain})' if domain else ''}:"
        return {
            "content": header + "\n" + "\n".join(lines),
            "success": True,
            "devices": [
                {
                    "entity_id": d.entity_id,
                    "name": d.name,
                    "domain": d.domain,
                    "state": d.state,
                    "last_synced": d.last_synced.isoformat() if d.last_synced else None,
                }
                for d in devices
            ],
            "source_agent": "smart_home",
        }

    def check_connection(self) -> dict[str, Any]:
        """Verify connectivity and authentication with Home Assistant.

        Constructs a HassClient and calls check_connection(). Raises
        HassAuthError immediately if token is missing (before any network call).

        Returns:
            Dict with "connected" (bool), "content" (str), "source_agent" (str).
        """
        try:
            with HassClient() as client:
                connected = client.check_connection()
        except HassAuthError as e:
            logger.warning(
                "check_connection: authentication error",
                exc_type=type(e).__name__,
                operation="check_connection",
            )
            return {
                "content": "Home Assistant access token is missing or empty. Cannot connect.",
                "connected": False,
                "success": False,
                "source_agent": "smart_home",
            }

        if connected:
            logger.info("check_connection: success", operation="check_connection")
            return {
                "content": "Home Assistant is reachable and the access token is valid.",
                "connected": True,
                "success": True,
                "source_agent": "smart_home",
            }

        logger.warning("check_connection: failed", operation="check_connection")
        return {
            "content": "Could not connect to Home Assistant. Check the URL and token.",
            "connected": False,
            "success": False,
            "source_agent": "smart_home",
        }

    # ------------------------------------------------------------------
    # Phase 7B: Control intent detection and confirmation gate
    # ------------------------------------------------------------------

    def _is_confirmation(self, query: str) -> bool:
        """Return True if the query is an explicit confirmation of a pending action.

        Checks whether there is an active pending action before returning True,
        so that isolated 'yes' messages do not trigger spurious confirmations.

        Args:
            query: Lowercased, stripped user input.

        Returns:
            True if query is a confirmation keyword AND a pending action exists.
        """
        if query not in _CONFIRMATION_KEYWORDS:
            return False
        # Only treat as confirmation if there is actually a pending action
        db = get_session("mind_db")
        try:
            pending = db.scalar(
                select(PendingSmartHomeAction).where(
                    PendingSmartHomeAction.status == "pending"
                )
            )
            return pending is not None
        finally:
            db.close()

    def _detect_control_intent(
        self, query: str
    ) -> tuple[str, str] | None:
        """Detect a device control intent in the user query.

        Scans for known service keywords and extracts the entity_id token.

        Args:
            query: Lowercased, stripped user input.

        Returns:
            (service, entity_id) if intent is detected and entity_id is found,
            None otherwise.
        """
        matched_service: str | None = None

        # Match service keywords from longest to shortest to prefer specific matches
        for phrase in sorted(_SERVICE_MAP, key=len, reverse=True):
            if phrase in query:
                matched_service = _SERVICE_MAP[phrase]
                break

        if matched_service is None:
            return None

        # Extract the first token that looks like an entity_id (contains a dot)
        tokens = query.split()
        entity_id = next((t for t in tokens if "." in t), None)
        if entity_id is None:
            return None

        # Validate entity_id format
        try:
            validate_entity_id(entity_id)
        except ValueError:
            return None

        return matched_service, entity_id

    def _request_confirmation(
        self, entity_id: str, domain: str, service: str
    ) -> dict[str, Any]:
        """Create a PendingSmartHomeAction and return a confirmation prompt.

        Validates that domain and service are in the allowlists before
        persisting anything. Cancels any previously pending action for the
        same entity before creating a new one.

        Args:
            entity_id: Target Home Assistant entity ID.
            domain: HA domain extracted from entity_id.
            service: Resolved HA service name.

        Returns:
            Response dict with confirmation prompt.
        """
        # Allowlist validation before touching the DB
        if domain not in ALLOWED_DOMAINS:
            return {
                "content": (
                    f"Control of domain '{domain}' is not permitted. "
                    f"Supported domains: {', '.join(sorted(ALLOWED_DOMAINS))}."
                ),
                "success": False,
                "source_agent": "smart_home",
            }
        if service not in ALLOWED_SERVICES:
            return {
                "content": (
                    f"Service '{service}' is not permitted. "
                    f"Supported services: {', '.join(sorted(ALLOWED_SERVICES))}."
                ),
                "success": False,
                "source_agent": "smart_home",
            }

        settings = get_settings()
        ttl_seconds = (
            settings.get("smart_home", {}).get("confirmation_ttl_seconds", _DEFAULT_CONFIRMATION_TTL)
        )
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=ttl_seconds)

        db = get_session("mind_db")
        try:
            # Cancel any pre-existing pending action
            self._cancel_pending_actions(db)

            pending = PendingSmartHomeAction(
                entity_id=entity_id,
                domain=domain,
                service=service,
                service_data={},
                requested_at=now,
                expires_at=expires_at,
                status="pending",
            )
            db.add(pending)
            db.commit()

            logger.info(
                "request_confirmation: pending action created",
                entity_id=entity_id,
                service=f"{domain}.{service}",
                expires_at=expires_at.isoformat(),
                operation="control",
            )
        except Exception:
            db.rollback()
            logger.exception("request_confirmation: DB error creating pending action")
            return {
                "content": "An unexpected error occurred while preparing the action. Please try again.",
                "success": False,
                "source_agent": "smart_home",
            }
        finally:
            db.close()

        # Human-readable service description
        service_display = service.replace("_", " ")
        return {
            "content": (
                f"This will {service_display} {entity_id}.\n"
                f"Do you want to continue? Reply 'yes' to confirm or anything else to cancel.\n"
                f"(This confirmation expires in {ttl_seconds // 60} minute(s).)"
            ),
            "success": True,
            "pending": True,
            "entity_id": entity_id,
            "service": service,
            "source_agent": "smart_home",
        }

    def _execute_confirmed_action(self) -> dict[str, Any]:
        """Retrieve the most recent pending action and execute it via HassClient.

        Fetches the newest pending action, checks it has not expired, calls
        HassClient.call_service(), and updates the status to 'executed'.

        Returns:
            Response dict with execution result.
        """
        db = get_session("mind_db")
        try:
            pending = db.scalar(
                select(PendingSmartHomeAction)
                .where(PendingSmartHomeAction.status == "pending")
                .order_by(PendingSmartHomeAction.requested_at.desc())
            )

            if pending is None:
                return {
                    "content": "No pending action found to confirm.",
                    "success": False,
                    "source_agent": "smart_home",
                }

            if pending.is_expired():
                pending.status = "expired"
                db.commit()
                logger.info(
                    "execute_confirmed_action: action expired",
                    entity_id=pending.entity_id,
                    operation="control",
                )
                return {
                    "content": (
                        "The confirmation window has expired. "
                        "Please repeat your command to try again."
                    ),
                    "success": False,
                    "source_agent": "smart_home",
                }

            entity_id = pending.entity_id
            domain = pending.domain
            service = pending.service
            service_data = pending.service_data or {}

        except Exception:
            db.rollback()
            logger.exception("execute_confirmed_action: DB error fetching pending action")
            return {
                "content": "An unexpected database error occurred. Please try again.",
                "success": False,
                "source_agent": "smart_home",
            }
        finally:
            db.close()

        # Execute the service call via HassClient
        try:
            with HassClient() as client:
                client.call_service(domain, service, entity_id, service_data or None)
        except HassAuthError as e:
            logger.warning(
                "execute_confirmed_action: authentication error",
                entity_id=entity_id,
                exc_type=type(e).__name__,
                operation="control",
            )
            self._mark_action_status(entity_id, "cancelled")
            return {
                "content": "Home Assistant authentication failed. Check your access token.",
                "success": False,
                "source_agent": "smart_home",
            }
        except HassServiceError as e:
            logger.warning(
                "execute_confirmed_action: service error",
                entity_id=entity_id,
                exc_type=type(e).__name__,
                operation="control",
            )
            self._mark_action_status(entity_id, "cancelled")
            return {
                "content": f"Service call failed: {e}",
                "success": False,
                "source_agent": "smart_home",
            }
        except (HassConnectionError, HassResponseError) as e:
            logger.warning(
                "execute_confirmed_action: connection/response error",
                entity_id=entity_id,
                exc_type=type(e).__name__,
                operation="control",
            )
            self._mark_action_status(entity_id, "cancelled")
            return {
                "content": f"Failed to reach Home Assistant: {type(e).__name__}",
                "success": False,
                "source_agent": "smart_home",
            }

        # Mark as executed
        self._mark_action_status(entity_id, "executed")
        service_display = service.replace("_", " ")
        logger.info(
            "execute_confirmed_action: success",
            entity_id=entity_id,
            service=f"{domain}.{service}",
            operation="control",
        )
        return {
            "content": f"Done. {service_display} executed on {entity_id}.",
            "success": True,
            "entity_id": entity_id,
            "service": service,
            "source_agent": "smart_home",
        }

    def _cancel_pending_actions(self, db: Any) -> None:
        """Cancel all currently pending actions.

        Called before creating a new pending action to ensure only one
        pending confirmation exists at a time.

        Args:
            db: Active SQLAlchemy Session. Caller is responsible for commit.
        """
        pending_rows = list(
            db.scalars(
                select(PendingSmartHomeAction).where(
                    PendingSmartHomeAction.status == "pending"
                )
            ).all()
        )
        for row in pending_rows:
            row.status = "cancelled"

    def _mark_action_status(self, entity_id: str, status: str) -> None:
        """Update the most recent pending action's status for the given entity.

        Args:
            entity_id: The entity ID of the pending action to update.
            status: New status value ('executed', 'expired', 'cancelled').
        """
        db = get_session("mind_db")
        try:
            pending = db.scalar(
                select(PendingSmartHomeAction)
                .where(PendingSmartHomeAction.entity_id == entity_id)
                .where(PendingSmartHomeAction.status == "pending")
                .order_by(PendingSmartHomeAction.requested_at.desc())
            )
            if pending is not None:
                pending.status = status
                db.commit()
        except Exception:
            db.rollback()
            logger.exception("_mark_action_status: DB error updating action status")
        finally:
            db.close()

    # ------------------------------------------------------------------
    # Phase 7A: Internal DB helper
    # ------------------------------------------------------------------

    def _upsert_device(self, db: Any, raw: dict[str, Any]) -> SmartDevice:
        """Insert or update a single SmartDevice row from a raw HASS state dict.

        Does NOT commit. The caller (sync_devices) is responsible for committing
        once after the full batch completes.

        Validates entity_id format before any DB operation.

        Args:
            db: An active SQLAlchemy Session.
            raw: A single state dictionary from GET /api/states.

        Returns:
            The created or updated SmartDevice ORM instance.

        Raises:
            KeyError: If required field 'entity_id' is missing from raw.
            ValueError: If entity_id does not match the HA format.
            TypeError: If raw is not a dict.
        """
        if not isinstance(raw, dict):
            raise TypeError(f"Expected dict, got {type(raw).__name__}")

        entity_id: str = raw["entity_id"]  # KeyError if missing

        # Validate format before reaching SQLAlchemy
        validate_entity_id(entity_id)

        domain = entity_id.split(".")[0]
        state_value = str(raw.get("state", "unknown"))
        attributes: dict[str, Any] = raw.get("attributes") or {}
        name = attributes.get("friendly_name") or entity_id

        def _parse_dt(value: Any) -> datetime | None:
            if not value:
                return None
            try:
                dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt
            except (ValueError, TypeError):
                return None

        last_changed = _parse_dt(raw.get("last_changed"))
        last_updated = _parse_dt(raw.get("last_updated"))
        now_utc = datetime.now(UTC)

        existing = db.scalar(
            select(SmartDevice).where(SmartDevice.entity_id == entity_id)
        )

        if existing:
            existing.name = name
            existing.domain = domain
            existing.state = state_value
            existing.attributes = attributes
            existing.last_changed = last_changed
            existing.last_updated = last_updated
            existing.last_synced = now_utc
            existing.updated_at = now_utc
            logger.debug(
                "upsert_device: updated",
                entity_id=entity_id,
                operation="update",
            )
            return existing

        device = SmartDevice(
            entity_id=entity_id,
            name=name,
            domain=domain,
            state=state_value,
            attributes=attributes,
            last_changed=last_changed,
            last_updated=last_updated,
            last_synced=now_utc,
            created_at=now_utc,
            updated_at=now_utc,
        )
        db.add(device)
        logger.debug(
            "upsert_device: inserted",
            entity_id=entity_id,
            operation="insert",
        )
        return device
