"""Unit tests for SmartHomeAgent (Phase 7A read-only + Phase 7B device control).

All tests use unittest.mock only. No real Home Assistant instance.
No real database beyond a temporary SQLite file (same fixture pattern
as test_house_agent.py).
"""
from __future__ import annotations

import os
import tempfile
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock, call, patch

import pytest

from renine.agents.base_agent import MemoryAccessLevel
from renine.agents.smart_home_agent import SmartHomeAgent
from renine.databases.models import MindBase
from renine.databases.models.pending_smart_home_action import PendingSmartHomeAction
from renine.databases.models.smart_device import SmartDevice
from renine.databases.session import _engines, _sessionmakers, get_engine, get_session
from renine.tools.permissions import PermissionLevel
from renine.tools.smart_home.hass_client import (
    ALLOWED_DOMAINS,
    ALLOWED_SERVICES,
    HassAuthError,
    HassConnectionError,
    HassResponseError,
    HassServiceError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def setup_mind_db():
    """Create an isolated temporary SQLite database for every test."""
    fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    _engines.clear()
    _sessionmakers.clear()

    mock_settings = {
        "databases": {"mind_db": temp_db_path},
        "features": {"smart_home_enabled": True},
        "smart_home": {"url": "http://localhost:8123", "token_env_var": "HASS_TOKEN"},
    }

    with patch("renine.databases.session.get_settings", return_value=mock_settings):
        engine = get_engine("mind_db")
        MindBase.metadata.create_all(bind=engine)
        yield temp_db_path

    _engines.clear()
    _sessionmakers.clear()
    if os.path.exists(temp_db_path):
        try:
            os.remove(temp_db_path)
        except OSError:
            pass


@pytest.fixture()
def agent():
    """Return a SmartHomeAgent with mocked settings that include the feature flag."""
    with patch(
        "renine.agents.smart_home_agent.get_settings",
        return_value={
            "features": {"smart_home_enabled": True},
            "smart_home": {"url": "http://localhost:8123", "token_env_var": "HASS_TOKEN"},
        },
    ):
        yield SmartHomeAgent()


def _make_raw(
    entity_id: str = "light.living_room",
    state: str = "on",
    friendly_name: str = "Living Room Light",
) -> dict[str, Any]:
    """Helper: create a minimal raw HASS state dict."""
    return {
        "entity_id": entity_id,
        "state": state,
        "attributes": {"friendly_name": friendly_name},
        "last_changed": "2024-01-01T00:00:00+00:00",
        "last_updated": "2024-01-01T00:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# 1. Manifest
# ---------------------------------------------------------------------------

class TestManifest:
    def test_manifest_name(self, agent: SmartHomeAgent) -> None:
        assert agent.get_manifest().name == "smart_home"

    def test_manifest_permission_standard(self, agent: SmartHomeAgent) -> None:
        assert agent.get_manifest().permission_level == PermissionLevel.STANDARD

    def test_manifest_active_phase(self, agent: SmartHomeAgent) -> None:
        assert agent.get_manifest().active_phase == 7

    def test_manifest_memory_access(self, agent: SmartHomeAgent) -> None:
        assert agent.get_manifest().memory_access_level == MemoryAccessLevel.LAYER1_AND_2


# ---------------------------------------------------------------------------
# 2. Security: no forbidden methods / no hidden HTTP
# ---------------------------------------------------------------------------

class TestSecurityConstraints:
    def test_no_forbidden_http_methods(self, agent: SmartHomeAgent) -> None:
        """Agent must have no POST/PUT/PATCH/DELETE/request attributes."""
        forbidden = ["post", "put", "patch", "delete", "request"]
        for method in forbidden:
            assert not hasattr(agent, method), (
                f"SmartHomeAgent must not have method '{method}'"
            )
            assert not hasattr(SmartHomeAgent, method)

    def test_no_httpx_import(self) -> None:
        """The agent module must not import httpx directly."""
        import renine.agents.smart_home_agent as module
        assert not hasattr(module, "httpx"), (
            "smart_home_agent.py must not import httpx at module level"
        )

    def test_no_requests_import(self) -> None:
        """The agent module must not import requests directly."""
        import renine.agents.smart_home_agent as module
        assert not hasattr(module, "requests"), (
            "smart_home_agent.py must not import requests"
        )


# ---------------------------------------------------------------------------
# 3. Feature flag
# ---------------------------------------------------------------------------

class TestFeatureFlag:
    def test_process_disabled_returns_graceful_message(self) -> None:
        """When smart_home_enabled=False, process() returns disabled message."""
        with patch(
            "renine.agents.smart_home_agent.get_settings",
            return_value={"features": {"smart_home_enabled": False}},
        ):
            ag = SmartHomeAgent()
            with patch("renine.agents.smart_home_agent.HassClient") as mock_client_cls:
                result = ag.process("sync devices")
                # Zero network calls
                mock_client_cls.assert_not_called()

        assert result["success"] is False
        assert "disabled" in result["content"].lower()

    def test_process_disabled_zero_network_calls(self) -> None:
        """Feature flag=False must suppress ALL network calls."""
        with patch(
            "renine.agents.smart_home_agent.get_settings",
            return_value={"features": {"smart_home_enabled": False}},
        ):
            ag = SmartHomeAgent()
            with patch("renine.agents.smart_home_agent.HassClient") as mock_cls:
                for query in ("sync", "status light.x", "list devices", "ping"):
                    ag.process(query)
                mock_cls.assert_not_called()


# ---------------------------------------------------------------------------
# 4. process() routing
# ---------------------------------------------------------------------------

class TestProcessRouting:
    def test_sync_keyword_routes_to_sync_devices(self, agent: SmartHomeAgent) -> None:
        with patch.object(agent, "sync_devices", return_value={"content": "ok", "success": True}) as mock_sync:
            with patch("renine.agents.smart_home_agent.get_settings",
                       return_value={"features": {"smart_home_enabled": True}}):
                agent.process("sync devices")
                mock_sync.assert_called_once()

    def test_discover_keyword_routes_to_sync_devices(self, agent: SmartHomeAgent) -> None:
        with patch.object(agent, "sync_devices", return_value={"content": "ok", "success": True}) as mock_sync:
            with patch("renine.agents.smart_home_agent.get_settings",
                       return_value={"features": {"smart_home_enabled": True}}):
                agent.process("discover all entities")
                mock_sync.assert_called_once()

    def test_status_keyword_routes_to_get_device_status(self, agent: SmartHomeAgent) -> None:
        with patch.object(agent, "get_device_status", return_value={"content": "on", "success": True}) as mock_status:
            with patch("renine.agents.smart_home_agent.get_settings",
                       return_value={"features": {"smart_home_enabled": True}}):
                agent.process("status light.living_room")
                mock_status.assert_called_once_with("light.living_room")

    def test_list_keyword_routes_to_list_cached(self, agent: SmartHomeAgent) -> None:
        with patch.object(agent, "list_cached_devices", return_value={"content": "[]", "success": True}) as mock_list:
            with patch("renine.agents.smart_home_agent.get_settings",
                       return_value={"features": {"smart_home_enabled": True}}):
                agent.process("list devices")
                mock_list.assert_called_once()

    def test_connection_keyword_routes_to_check_connection(self, agent: SmartHomeAgent) -> None:
        with patch.object(agent, "check_connection", return_value={"content": "ok", "connected": True, "success": True}) as mock_conn:
            with patch("renine.agents.smart_home_agent.get_settings",
                       return_value={"features": {"smart_home_enabled": True}}):
                agent.process("connection")
                mock_conn.assert_called_once()

    def test_unknown_query_returns_help(self, agent: SmartHomeAgent) -> None:
        with patch("renine.agents.smart_home_agent.get_settings",
                   return_value={"features": {"smart_home_enabled": True}}):
            result = agent.process("what is the weather?")
        assert result["success"] is True
        assert "read-only" in result["content"].lower() or "sync" in result["content"].lower()

    def test_status_without_entity_id_returns_error(self, agent: SmartHomeAgent) -> None:
        with patch("renine.agents.smart_home_agent.get_settings",
                   return_value={"features": {"smart_home_enabled": True}}):
            result = agent.process("status")
        assert result["success"] is False
        assert "entity" in result["content"].lower()


# ---------------------------------------------------------------------------
# 5. sync_devices()
# ---------------------------------------------------------------------------

class TestSyncDevices:
    def test_sync_success_inserts_rows(self, agent: SmartHomeAgent) -> None:
        """discover_entities() returning 2 entities → 2 rows in DB."""
        entities = [
            _make_raw("light.living_room", "on", "Living Room"),
            _make_raw("switch.kitchen", "off", "Kitchen Switch"),
        ]
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.discover_entities.return_value = entities

        with patch("renine.agents.smart_home_agent.HassClient", return_value=mock_client):
            result = agent.sync_devices()

        assert result["success"] is True
        assert result["synced"] == 2
        assert result["errors"] == 0

    def test_sync_upsert_updates_existing_row(self, agent: SmartHomeAgent) -> None:
        """Calling sync_devices() twice on the same entity updates (not duplicates) the row."""
        raw = _make_raw("light.living_room", "on", "Living Room")
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.discover_entities.return_value = [raw]

        with patch("renine.agents.smart_home_agent.HassClient", return_value=mock_client):
            agent.sync_devices()

        # Second sync with updated state
        raw_updated = _make_raw("light.living_room", "off", "Living Room")
        mock_client.discover_entities.return_value = [raw_updated]

        with patch("renine.agents.smart_home_agent.HassClient", return_value=mock_client):
            result = agent.sync_devices()

        assert result["synced"] == 1
        assert result["errors"] == 0

        # Verify only one row in DB
        from renine.databases.session import get_session
        from sqlalchemy import select
        db = get_session("mind_db")
        try:
            rows = list(db.scalars(select(SmartDevice)).all())
            assert len(rows) == 1
            assert rows[0].state == "off"
        finally:
            db.close()

    def test_sync_single_commit_after_loop(self, agent: SmartHomeAgent) -> None:
        """Only one DB commit is issued after the full entity loop."""
        entities = [_make_raw("light.a"), _make_raw("switch.b", "off")]
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.discover_entities.return_value = entities

        mock_session = MagicMock()
        mock_session.scalar.return_value = None  # No existing rows

        with patch("renine.agents.smart_home_agent.HassClient", return_value=mock_client):
            with patch("renine.agents.smart_home_agent.get_session", return_value=mock_session):
                agent.sync_devices()

        # commit must be called exactly once
        mock_session.commit.assert_called_once()

    def test_sync_malformed_entity_continues(self, agent: SmartHomeAgent) -> None:
        """A malformed entity in the batch is skipped; remaining entities are still processed."""
        entities = [
            {"state": "on"},                          # missing entity_id → KeyError
            _make_raw("sensor.temp", "21.5", "Temp"), # valid
        ]
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.discover_entities.return_value = entities

        with patch("renine.agents.smart_home_agent.HassClient", return_value=mock_client):
            result = agent.sync_devices()

        assert result["success"] is True
        assert result["synced"] == 1
        assert result["errors"] == 1
        assert "skipped" in result["content"].lower()

    def test_sync_rollback_on_db_exception(self, agent: SmartHomeAgent) -> None:
        """Unexpected DB exception causes rollback and error response."""
        entities = [_make_raw()]
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.discover_entities.return_value = entities

        mock_session = MagicMock()
        mock_session.scalar.return_value = None
        mock_session.commit.side_effect = RuntimeError("disk full")

        with patch("renine.agents.smart_home_agent.HassClient", return_value=mock_client):
            with patch("renine.agents.smart_home_agent.get_session", return_value=mock_session):
                result = agent.sync_devices()

        mock_session.rollback.assert_called_once()
        assert result["success"] is False
        assert "rolled back" in result["content"].lower()

    def test_sync_hass_connection_error(self, agent: SmartHomeAgent) -> None:
        """HassConnectionError from discover_entities → error response, no DB call."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.discover_entities.side_effect = HassConnectionError("timeout")

        with patch("renine.agents.smart_home_agent.HassClient", return_value=mock_client):
            with patch("renine.agents.smart_home_agent.get_session") as mock_get_session:
                result = agent.sync_devices()
                mock_get_session.assert_not_called()

        assert result["success"] is False

    def test_sync_auth_error(self, agent: SmartHomeAgent) -> None:
        """HassAuthError on discover → auth error message."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.discover_entities.side_effect = HassAuthError("bad token")

        with patch("renine.agents.smart_home_agent.HassClient", return_value=mock_client):
            result = agent.sync_devices()

        assert result["success"] is False
        assert "authentication" in result["content"].lower()


# ---------------------------------------------------------------------------
# 6. get_device_status()
# ---------------------------------------------------------------------------

class TestGetDeviceStatus:
    def test_success_returns_state(self, agent: SmartHomeAgent) -> None:
        state_data = {
            "entity_id": "light.living_room",
            "state": "on",
            "attributes": {"friendly_name": "Living Room Light"},
        }
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get_entity_state.return_value = state_data

        with patch("renine.agents.smart_home_agent.HassClient", return_value=mock_client):
            result = agent.get_device_status("light.living_room")

        assert result["success"] is True
        assert result["state"] == "on"
        assert result["entity_id"] == "light.living_room"
        assert "on" in result["content"]

    def test_not_found_returns_graceful_message(self, agent: SmartHomeAgent) -> None:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get_entity_state.return_value = None  # 404

        with patch("renine.agents.smart_home_agent.HassClient", return_value=mock_client):
            result = agent.get_device_status("light.nonexistent")

        assert result["success"] is True
        assert result["state"] is None
        assert "not found" in result["content"].lower()

    def test_invalid_entity_id_raises_before_network(self, agent: SmartHomeAgent) -> None:
        """Invalid entity_id → ValueError caught, no network call made."""
        with patch("renine.agents.smart_home_agent.HassClient") as mock_cls:
            result = agent.get_device_status("invalid_no_dot")
            mock_cls.assert_not_called()

        assert result["success"] is False
        assert "invalid entity id" in result["content"].lower()

    def test_auth_error_returns_error_message(self, agent: SmartHomeAgent) -> None:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get_entity_state.side_effect = HassAuthError("401")

        with patch("renine.agents.smart_home_agent.HassClient", return_value=mock_client):
            result = agent.get_device_status("light.living_room")

        assert result["success"] is False
        assert "authentication" in result["content"].lower()

    def test_connection_error_returns_error_message(self, agent: SmartHomeAgent) -> None:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.get_entity_state.side_effect = HassConnectionError("timeout")

        with patch("renine.agents.smart_home_agent.HassClient", return_value=mock_client):
            result = agent.get_device_status("sensor.temperature")

        assert result["success"] is False


# ---------------------------------------------------------------------------
# 7. list_cached_devices()
# ---------------------------------------------------------------------------

class TestListCachedDevices:
    def _seed(self, agent: SmartHomeAgent, entities: list[dict]) -> None:
        """Seed the DB by running a sync with mock entities."""
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.discover_entities.return_value = entities

        with patch("renine.agents.smart_home_agent.HassClient", return_value=mock_client):
            agent.sync_devices()

    def test_empty_cache_returns_message(self, agent: SmartHomeAgent) -> None:
        result = agent.list_cached_devices()
        assert result["success"] is True
        assert result["devices"] == []
        assert "no devices" in result["content"].lower()

    def test_lists_all_cached_devices(self, agent: SmartHomeAgent) -> None:
        self._seed(agent, [
            _make_raw("light.kitchen", "on"),
            _make_raw("switch.garage", "off"),
        ])
        result = agent.list_cached_devices()
        assert result["success"] is True
        assert len(result["devices"]) == 2
        entity_ids = {d["entity_id"] for d in result["devices"]}
        assert entity_ids == {"light.kitchen", "switch.garage"}

    def test_domain_filter(self, agent: SmartHomeAgent) -> None:
        self._seed(agent, [
            _make_raw("light.kitchen", "on"),
            _make_raw("switch.garage", "off"),
            _make_raw("light.bedroom", "off"),
        ])
        result = agent.list_cached_devices(domain="light")
        assert result["success"] is True
        assert len(result["devices"]) == 2
        for d in result["devices"]:
            assert d["entity_id"].startswith("light.")

    def test_no_network_call(self, agent: SmartHomeAgent) -> None:
        """list_cached_devices() is a pure DB read — no HassClient created."""
        with patch("renine.agents.smart_home_agent.HassClient") as mock_cls:
            agent.list_cached_devices()
            mock_cls.assert_not_called()


# ---------------------------------------------------------------------------
# 8. check_connection()
# ---------------------------------------------------------------------------

class TestCheckConnection:
    def test_connected_returns_true(self, agent: SmartHomeAgent) -> None:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.check_connection.return_value = True

        with patch("renine.agents.smart_home_agent.HassClient", return_value=mock_client):
            result = agent.check_connection()

        assert result["connected"] is True
        assert result["success"] is True

    def test_disconnected_returns_false(self, agent: SmartHomeAgent) -> None:
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.check_connection.return_value = False

        with patch("renine.agents.smart_home_agent.HassClient", return_value=mock_client):
            result = agent.check_connection()

        assert result["connected"] is False
        assert result["success"] is False

    def test_auth_error_on_init(self, agent: SmartHomeAgent) -> None:
        """HassAuthError raised during HassClient() construction is caught gracefully."""
        with patch(
            "renine.agents.smart_home_agent.HassClient",
            side_effect=HassAuthError("missing token"),
        ):
            result = agent.check_connection()

        assert result["connected"] is False
        assert result["success"] is False
        assert "token" in result["content"].lower()


# ---------------------------------------------------------------------------
# 9. _upsert_device() internals
# ---------------------------------------------------------------------------

class TestUpsertDevice:
    def test_insert_new_device(self, agent: SmartHomeAgent) -> None:
        from renine.databases.session import get_session
        from sqlalchemy import select

        db = get_session("mind_db")
        try:
            agent._upsert_device(db, _make_raw("light.hall", "on", "Hallway"))
            db.commit()
            result = db.scalar(select(SmartDevice).where(SmartDevice.entity_id == "light.hall"))
        finally:
            db.close()

        assert result is not None
        assert result.state == "on"
        assert result.name == "Hallway"
        assert result.domain == "light"

    def test_update_existing_device(self, agent: SmartHomeAgent) -> None:
        from renine.databases.session import get_session
        from sqlalchemy import select

        db = get_session("mind_db")
        try:
            # Insert
            agent._upsert_device(db, _make_raw("light.hall", "on", "Hallway"))
            db.commit()

            # Update
            agent._upsert_device(db, _make_raw("light.hall", "off", "Hallway"))
            db.commit()

            rows = list(db.scalars(select(SmartDevice)).all())
        finally:
            db.close()

        assert len(rows) == 1
        assert rows[0].state == "off"

    def test_missing_entity_id_raises_key_error(self, agent: SmartHomeAgent) -> None:
        from renine.databases.session import get_session

        db = get_session("mind_db")
        try:
            with pytest.raises(KeyError):
                agent._upsert_device(db, {"state": "on"})
        finally:
            db.close()

    def test_invalid_entity_id_raises_value_error(self, agent: SmartHomeAgent) -> None:
        from renine.databases.session import get_session

        db = get_session("mind_db")
        try:
            with pytest.raises(ValueError):
                agent._upsert_device(db, {"entity_id": "invalid_format", "state": "on"})
        finally:
            db.close()

    def test_non_dict_raises_type_error(self, agent: SmartHomeAgent) -> None:
        from renine.databases.session import get_session

        db = get_session("mind_db")
        try:
            with pytest.raises(TypeError):
                agent._upsert_device(db, "not a dict")  # type: ignore
        finally:
            db.close()

    def test_last_synced_is_timezone_aware(self, agent: SmartHomeAgent) -> None:
        from renine.databases.session import get_session

        db = get_session("mind_db")
        try:
            device = agent._upsert_device(db, _make_raw())
            assert device.last_synced.tzinfo is not None
            db.commit()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 10. Phase 7B — HassClient allowlists (unit, no network)
# ---------------------------------------------------------------------------

class TestHassClientAllowlists:
    def test_allowed_domains_contains_expected(self) -> None:
        assert "light" in ALLOWED_DOMAINS
        assert "switch" in ALLOWED_DOMAINS
        assert "fan" in ALLOWED_DOMAINS
        assert "cover" in ALLOWED_DOMAINS

    def test_allowed_domains_excludes_forbidden(self) -> None:
        assert "lock" not in ALLOWED_DOMAINS
        assert "alarm_control_panel" not in ALLOWED_DOMAINS
        assert "climate" not in ALLOWED_DOMAINS

    def test_allowed_services_contains_expected(self) -> None:
        assert "turn_on" in ALLOWED_SERVICES
        assert "turn_off" in ALLOWED_SERVICES
        assert "toggle" in ALLOWED_SERVICES
        assert "open_cover" in ALLOWED_SERVICES
        assert "close_cover" in ALLOWED_SERVICES
        assert "stop_cover" in ALLOWED_SERVICES

    def test_call_service_disallowed_domain_raises_no_network(self) -> None:
        """Disallowed domain raises HassServiceError before any network call."""
        from renine.tools.smart_home.hass_client import HassClient, HassServiceError
        import os
        os.environ["HASS_TOKEN"] = "test_token"
        try:
            with patch(
                "renine.tools.smart_home.hass_client.get_settings",
                return_value={"smart_home": {"url": "http://localhost:8123", "token_env_var": "HASS_TOKEN"}},
            ):
                with HassClient() as client:
                    with patch.object(client, "_post") as mock_post:
                        with pytest.raises(HassServiceError, match="not in the allowed list"):
                            client.call_service("lock", "lock", "lock.front_door")
                        mock_post.assert_not_called()
        finally:
            del os.environ["HASS_TOKEN"]

    def test_call_service_disallowed_service_raises_no_network(self) -> None:
        """Disallowed service raises HassServiceError before any network call."""
        from renine.tools.smart_home.hass_client import HassClient, HassServiceError
        import os
        os.environ["HASS_TOKEN"] = "test_token"
        try:
            with patch(
                "renine.tools.smart_home.hass_client.get_settings",
                return_value={"smart_home": {"url": "http://localhost:8123", "token_env_var": "HASS_TOKEN"}},
            ):
                with HassClient() as client:
                    with patch.object(client, "_post") as mock_post:
                        with pytest.raises(HassServiceError, match="not in the allowed list"):
                            client.call_service("light", "set_temperature", "light.x")
                        mock_post.assert_not_called()
        finally:
            del os.environ["HASS_TOKEN"]

    def test_call_service_success(self) -> None:
        """Happy path: call_service() calls _post and returns parsed data."""
        from renine.tools.smart_home.hass_client import HassClient
        import os
        os.environ["HASS_TOKEN"] = "test_token"
        try:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '[]'
            mock_response.json.return_value = []
            mock_response.raise_for_status = MagicMock()

            with patch(
                "renine.tools.smart_home.hass_client.get_settings",
                return_value={"smart_home": {"url": "http://localhost:8123", "token_env_var": "HASS_TOKEN"}},
            ):
                with HassClient() as client:
                    with patch.object(client, "_post", return_value=mock_response):
                        result = client.call_service("light", "turn_on", "light.living_room")
            assert isinstance(result, dict)
        finally:
            del os.environ["HASS_TOKEN"]

    def test_call_service_invalid_entity_id_raises_value_error(self) -> None:
        """Invalid entity_id format raises ValueError before network call."""
        from renine.tools.smart_home.hass_client import HassClient
        import os
        os.environ["HASS_TOKEN"] = "test_token"
        try:
            with patch(
                "renine.tools.smart_home.hass_client.get_settings",
                return_value={"smart_home": {"url": "http://localhost:8123", "token_env_var": "HASS_TOKEN"}},
            ):
                with HassClient() as client:
                    with patch.object(client, "_post") as mock_post:
                        with pytest.raises(ValueError):
                            client.call_service("light", "turn_on", "invalid_no_dot")
                        mock_post.assert_not_called()
        finally:
            del os.environ["HASS_TOKEN"]


# ---------------------------------------------------------------------------
# 11. Phase 7B — Control intent detection
# ---------------------------------------------------------------------------

class TestControlIntentDetection:
    def test_turn_on_detected(self, agent: SmartHomeAgent) -> None:
        result = agent._detect_control_intent("turn on light.living_room")
        assert result is not None
        service, entity_id = result
        assert service == "turn_on"
        assert entity_id == "light.living_room"

    def test_turn_off_detected(self, agent: SmartHomeAgent) -> None:
        result = agent._detect_control_intent("turn off switch.kitchen")
        assert result is not None
        service, entity_id = result
        assert service == "turn_off"
        assert entity_id == "switch.kitchen"

    def test_toggle_detected(self, agent: SmartHomeAgent) -> None:
        result = agent._detect_control_intent("toggle fan.bedroom")
        assert result is not None
        service, entity_id = result
        assert service == "toggle"
        assert entity_id == "fan.bedroom"

    def test_open_cover_detected(self, agent: SmartHomeAgent) -> None:
        result = agent._detect_control_intent("open cover.garage")
        assert result is not None
        service, entity_id = result
        assert service == "open_cover"
        assert entity_id == "cover.garage"

    def test_close_cover_detected(self, agent: SmartHomeAgent) -> None:
        result = agent._detect_control_intent("close cover.garage")
        assert result is not None
        service, entity_id = result
        assert service == "close_cover"
        assert entity_id == "cover.garage"

    def test_stop_cover_detected(self, agent: SmartHomeAgent) -> None:
        result = agent._detect_control_intent("stop cover.garage")
        assert result is not None
        service, entity_id = result
        assert service == "stop_cover"
        assert entity_id == "cover.garage"

    def test_no_entity_id_returns_none(self, agent: SmartHomeAgent) -> None:
        result = agent._detect_control_intent("turn on the lights")
        assert result is None

    def test_invalid_entity_id_returns_none(self, agent: SmartHomeAgent) -> None:
        result = agent._detect_control_intent("turn on INVALID")
        assert result is None

    def test_read_query_returns_none(self, agent: SmartHomeAgent) -> None:
        result = agent._detect_control_intent("what is the status of light.living_room")
        assert result is None


# ---------------------------------------------------------------------------
# 12. Phase 7B — Confirmation gate
# ---------------------------------------------------------------------------

class TestConfirmationGate:
    def test_request_confirmation_creates_pending_action(self, agent: SmartHomeAgent) -> None:
        """request_confirmation() persists a PendingSmartHomeAction with status=pending."""
        with patch(
            "renine.agents.smart_home_agent.get_settings",
            return_value={
                "features": {"smart_home_enabled": True},
                "smart_home": {"url": "http://localhost:8123", "token_env_var": "HASS_TOKEN",
                               "confirmation_ttl_seconds": 300},
            },
        ):
            result = agent._request_confirmation("light.living_room", "light", "turn_on")

        assert result["success"] is True
        assert result["pending"] is True
        assert "confirm" in result["content"].lower() or "continue" in result["content"].lower()

        db = get_session("mind_db")
        try:
            from sqlalchemy import select
            pending = db.scalar(
                select(PendingSmartHomeAction).where(
                    PendingSmartHomeAction.status == "pending"
                )
            )
            assert pending is not None
            assert pending.entity_id == "light.living_room"
            assert pending.service == "turn_on"
        finally:
            db.close()

    def test_disallowed_domain_no_db_write(self, agent: SmartHomeAgent) -> None:
        """Disallowed domain returns error without writing to DB."""
        result = agent._request_confirmation("lock.front_door", "lock", "lock")
        assert result["success"] is False
        assert "not permitted" in result["content"].lower()

        db = get_session("mind_db")
        try:
            from sqlalchemy import select
            count = db.scalar(
                select(PendingSmartHomeAction).where(
                    PendingSmartHomeAction.status == "pending"
                )
            )
            assert count is None
        finally:
            db.close()

    def test_is_confirmation_true_when_pending_exists(self, agent: SmartHomeAgent) -> None:
        """_is_confirmation() returns True when a pending action exists."""
        now = datetime.now(UTC)
        db = get_session("mind_db")
        try:
            pending = PendingSmartHomeAction(
                entity_id="light.x",
                domain="light",
                service="turn_on",
                service_data={},
                requested_at=now,
                expires_at=now + timedelta(seconds=300),
                status="pending",
            )
            db.add(pending)
            db.commit()
        finally:
            db.close()

        assert agent._is_confirmation("yes") is True

    def test_is_confirmation_false_without_pending(self, agent: SmartHomeAgent) -> None:
        """_is_confirmation() returns False when no pending action exists."""
        assert agent._is_confirmation("yes") is False

    def test_is_confirmation_false_for_non_confirmation_word(self, agent: SmartHomeAgent) -> None:
        """Non-confirmation words return False even when a pending action exists."""
        now = datetime.now(UTC)
        db = get_session("mind_db")
        try:
            pending = PendingSmartHomeAction(
                entity_id="light.x",
                domain="light",
                service="turn_on",
                service_data={},
                requested_at=now,
                expires_at=now + timedelta(seconds=300),
                status="pending",
            )
            db.add(pending)
            db.commit()
        finally:
            db.close()

        assert agent._is_confirmation("no") is False
        assert agent._is_confirmation("cancel") is False
        assert agent._is_confirmation("what?") is False

    def test_full_confirmation_flow(self, agent: SmartHomeAgent) -> None:
        """Full happy path: request → confirm → execute → DB status is executed."""
        with patch(
            "renine.agents.smart_home_agent.get_settings",
            return_value={
                "features": {"smart_home_enabled": True},
                "smart_home": {
                    "url": "http://localhost:8123",
                    "token_env_var": "HASS_TOKEN",
                    "confirmation_ttl_seconds": 300,
                },
            },
        ):
            # Step 1: request confirmation
            confirm_result = agent._request_confirmation("switch.kitchen", "switch", "turn_off")
        assert confirm_result["success"] is True
        assert confirm_result["pending"] is True

        # Step 2: execute via mock HassClient
        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.call_service.return_value = {}

        with patch("renine.agents.smart_home_agent.HassClient", return_value=mock_client):
            exec_result = agent._execute_confirmed_action()

        assert exec_result["success"] is True
        assert "turn off" in exec_result["content"].lower() or "executed" in exec_result["content"].lower()
        mock_client.call_service.assert_called_once_with("switch", "turn_off", "switch.kitchen", None)

        # Step 3: verify DB status is 'executed'
        db = get_session("mind_db")
        try:
            from sqlalchemy import select
            action = db.scalar(
                select(PendingSmartHomeAction).where(
                    PendingSmartHomeAction.entity_id == "switch.kitchen"
                )
            )
            assert action is not None
            assert action.status == "executed"
        finally:
            db.close()

    def test_expired_action_is_rejected(self, agent: SmartHomeAgent) -> None:
        """An expired pending action is rejected and marked expired in the DB."""
        now = datetime.now(UTC)
        db = get_session("mind_db")
        try:
            expired = PendingSmartHomeAction(
                entity_id="fan.bedroom",
                domain="fan",
                service="turn_off",
                service_data={},
                requested_at=now - timedelta(seconds=400),
                expires_at=now - timedelta(seconds=100),  # already expired
                status="pending",
            )
            db.add(expired)
            db.commit()
        finally:
            db.close()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)

        with patch("renine.agents.smart_home_agent.HassClient", return_value=mock_client):
            result = agent._execute_confirmed_action()

        assert result["success"] is False
        assert "expired" in result["content"].lower()
        # Verify no service call was made
        mock_client.call_service.assert_not_called()

        db = get_session("mind_db")
        try:
            from sqlalchemy import select
            action = db.scalar(
                select(PendingSmartHomeAction).where(
                    PendingSmartHomeAction.entity_id == "fan.bedroom"
                )
            )
            assert action.status == "expired"
        finally:
            db.close()

    def test_no_pending_action_execute_returns_error(self, agent: SmartHomeAgent) -> None:
        """_execute_confirmed_action() with no pending action returns error response."""
        result = agent._execute_confirmed_action()
        assert result["success"] is False
        assert "no pending action" in result["content"].lower()

    def test_hass_auth_error_on_execute_cancels_action(self, agent: SmartHomeAgent) -> None:
        """HassAuthError during execute marks action as cancelled."""
        now = datetime.now(UTC)
        db = get_session("mind_db")
        try:
            pending = PendingSmartHomeAction(
                entity_id="light.hall",
                domain="light",
                service="turn_on",
                service_data={},
                requested_at=now,
                expires_at=now + timedelta(seconds=300),
                status="pending",
            )
            db.add(pending)
            db.commit()
        finally:
            db.close()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.call_service.side_effect = HassAuthError("token expired")

        with patch("renine.agents.smart_home_agent.HassClient", return_value=mock_client):
            result = agent._execute_confirmed_action()

        assert result["success"] is False
        assert "authentication" in result["content"].lower()

    def test_hass_service_error_on_execute_cancels_action(self, agent: SmartHomeAgent) -> None:
        """HassServiceError during execute returns failure response."""
        now = datetime.now(UTC)
        db = get_session("mind_db")
        try:
            pending = PendingSmartHomeAction(
                entity_id="light.hall",
                domain="light",
                service="turn_on",
                service_data={},
                requested_at=now,
                expires_at=now + timedelta(seconds=300),
                status="pending",
            )
            db.add(pending)
            db.commit()
        finally:
            db.close()

        mock_client = MagicMock()
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.call_service.side_effect = HassServiceError("service failed")

        with patch("renine.agents.smart_home_agent.HassClient", return_value=mock_client):
            result = agent._execute_confirmed_action()

        assert result["success"] is False
        assert "service call failed" in result["content"].lower()

    def test_process_routes_control_intent_to_confirmation(self, agent: SmartHomeAgent) -> None:
        """process() with a control-intent query calls _request_confirmation()."""
        with patch.object(
            agent, "_request_confirmation",
            return_value={"content": "confirm?", "success": True, "pending": True}
        ) as mock_confirm:
            with patch(
                "renine.agents.smart_home_agent.get_settings",
                return_value={"features": {"smart_home_enabled": True},
                              "smart_home": {"confirmation_ttl_seconds": 300}},
            ):
                result = agent.process("turn on light.living_room")
            mock_confirm.assert_called_once_with("light.living_room", "light", "turn_on")

    def test_process_routes_yes_to_execute(self, agent: SmartHomeAgent) -> None:
        """process() with 'yes' when pending action exists calls _execute_confirmed_action()."""
        now = datetime.now(UTC)
        db = get_session("mind_db")
        try:
            pending = PendingSmartHomeAction(
                entity_id="switch.x",
                domain="switch",
                service="turn_off",
                service_data={},
                requested_at=now,
                expires_at=now + timedelta(seconds=300),
                status="pending",
            )
            db.add(pending)
            db.commit()
        finally:
            db.close()

        with patch.object(
            agent, "_execute_confirmed_action",
            return_value={"content": "done", "success": True}
        ) as mock_exec:
            with patch(
                "renine.agents.smart_home_agent.get_settings",
                return_value={"features": {"smart_home_enabled": True}},
            ):
                result = agent.process("yes")
            mock_exec.assert_called_once()

    def test_process_no_network_call_on_disallowed_domain(self, agent: SmartHomeAgent) -> None:
        """Control intent with disallowed domain returns error, no HassClient created."""
        with patch("renine.agents.smart_home_agent.HassClient") as mock_cls:
            with patch(
                "renine.agents.smart_home_agent.get_settings",
                return_value={"features": {"smart_home_enabled": True},
                              "smart_home": {"confirmation_ttl_seconds": 300}},
            ):
                result = agent.process("turn on lock.front_door")
            mock_cls.assert_not_called()
        assert result["success"] is False
