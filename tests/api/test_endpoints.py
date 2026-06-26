"""Milestone 2 integration and unit tests for Renine Mobile API endpoints.

Covers:
    - Authentication checks (401 Unauthorized for missing/bad tokens)
    - Memory context, history, mind, and personality endpoints
    - Whitelist validation and sanitization checks
    - Smart Home devices and action creation/confirmation endpoints
    - Pet listing and feeding endpoints
    - Reminder listing endpoints
"""
from __future__ import annotations

import datetime
import os
from typing import Generator
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from api.server import create_app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    """TestClient with API_PASSWORD environment variable patched."""
    with patch.dict(os.environ, {"API_PASSWORD": "renine-secret-password-123"}):
        test_app = create_app()
        with TestClient(test_app, raise_server_exceptions=False) as c:
            yield c


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    """Return authorization headers with a valid admin JWT."""
    from api.auth import create_access_token
    token = create_access_token({"sub": "admin"})
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Authentication Tests (all endpoints require auth)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "method, url, json_body",
    [
        ("GET", "/api/memory/context", None),
        ("GET", "/api/memory/history", None),
        ("GET", "/api/memory/mind?namespace=house", None),
        ("GET", "/api/memory/personality", None),
        ("GET", "/api/smart-home/devices", None),
        ("GET", "/api/smart-home/devices/light.living_room", None),
        ("POST", "/api/smart-home/actions", {"entity_id": "light.living_room", "service": "turn_on"}),
        ("POST", "/api/smart-home/actions/123/confirm", None),
        ("GET", "/api/pets", None),
        ("POST", "/api/pets/Buddy/feed", None),
        ("GET", "/api/reminders", None),
    ],
)
def test_endpoints_require_auth(client: TestClient, method: str, url: str, json_body: dict | None) -> None:
    """All data endpoints must reject requests with 401 Unauthorized if no JWT is supplied."""
    if method == "GET":
        resp = client.get(url)
    else:
        resp = client.post(url, json=json_body)
    assert resp.status_code == 401
    assert "detail" in resp.json()


# ---------------------------------------------------------------------------
# Memory Endpoints
# ---------------------------------------------------------------------------

def test_get_memory_context_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    """GET /api/memory/context returns messages and correct count."""
    mock_messages = [
        {"role": "user", "content": "Hello Renine"},
        {"role": "assistant", "content": "Hello! How can I help you?"},
    ]
    with patch("api.endpoints.get_layer1_context", return_value=mock_messages) as mock_helper:
        resp = client.get("/api/memory/context", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 2
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["content"] == "Hello Renine"
        mock_helper.assert_called_once()


def test_get_memory_history_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    """GET /api/memory/history returns conversation summary list."""
    mock_history = [
        {
            "id": 1,
            "date": "2026-06-26T12:00:00",
            "summary": "Discussed groceries",
            "created_at": "2026-06-26T12:00:00",
        }
    ]
    with patch("api.endpoints.get_layer2_history", return_value=mock_history) as mock_helper:
        resp = client.get("/api/memory/history?limit=10", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["conversations"][0]["summary"] == "Discussed groceries"
        mock_helper.assert_called_once_with(limit=10)


def test_get_memory_mind_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    """GET /api/memory/mind returns whitelisted mind database records."""
    mock_records = [
        {
            "id": 5,
            "namespace": "house",
            "key": "living_room_temp",
            "summary": "Temperature is 22 degrees",
            "created_at": "2026-06-26T12:00:00",
            "updated_at": "2026-06-26T12:05:00",
        }
    ]
    with patch("api.endpoints.get_layer3_mind", return_value=mock_records) as mock_helper:
        resp = client.get("/api/memory/mind?namespace=house&query=temp&limit=5", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["namespace"] == "house"
        assert data["records"][0]["key"] == "living_room_temp"
        assert data["records"][0]["summary"] == "Temperature is 22 degrees"
        mock_helper.assert_called_once_with(namespace="house", query="temp", limit=5)


def test_get_memory_personality_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    """GET /api/memory/personality returns whitelisted person profiles."""
    mock_people = [
        {
            "name": "Alice",
            "relationship": "sister",
            "age": 30,
            "birthday": "1996-03-12",
            "updated_at": "2026-06-26T12:00:00",
        }
    ]
    with patch("api.endpoints.get_layer4_personality", return_value=mock_people) as mock_helper:
        resp = client.get("/api/memory/personality?query=sister&limit=2", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["people"][0]["name"] == "Alice"
        assert data["people"][0]["relationship"] == "sister"
        mock_helper.assert_called_once_with(query="sister", limit=2)


# ---------------------------------------------------------------------------
# Smart Home Endpoints
# ---------------------------------------------------------------------------

def test_list_devices_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    """GET /api/smart-home/devices returns list of devices."""
    mock_devices = [
        {
            "id": 1,
            "entity_id": "light.kitchen",
            "name": "Kitchen Light",
            "domain": "light",
            "state": "off",
            "last_synced": "2026-06-26T12:00:00",
            "updated_at": "2026-06-26T12:00:00",
        }
    ]
    with patch("api.endpoints.get_smart_devices", return_value=mock_devices) as mock_helper:
        resp = client.get("/api/smart-home/devices?domain=light", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["devices"][0]["entity_id"] == "light.kitchen"
        mock_helper.assert_called_once_with(domain="light")


def test_get_device_state_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    """GET /api/smart-home/devices/{entity_id} returns state and attributes."""
    mock_device = {
        "entity_id": "light.kitchen",
        "name": "Kitchen Light",
        "domain": "light",
        "state": "on",
        "attributes": {"brightness": 200},
        "last_synced": "2026-06-26T12:00:00",
    }
    with patch("api.endpoints.get_smart_device_by_entity", return_value=mock_device) as mock_helper:
        resp = client.get("/api/smart-home/devices/light.kitchen", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_id"] == "light.kitchen"
        assert data["attributes"]["brightness"] == 200
        mock_helper.assert_called_once_with("light.kitchen")


def test_get_device_state_not_found(client: TestClient, auth_headers: dict[str, str]) -> None:
    """GET /api/smart-home/devices/{entity_id} returns 404 if not cached."""
    with patch("api.endpoints.get_smart_device_by_entity", return_value=None):
        resp = client.get("/api/smart-home/devices/light.unknown", headers=auth_headers)
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]


def test_create_action_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    """POST /api/smart-home/actions creates and returns a pending action."""
    mock_action = {
        "id": 42,
        "entity_id": "light.kitchen",
        "domain": "light",
        "service": "turn_on",
        "status": "pending",
        "requested_at": "2026-06-26T12:00:00",
        "expires_at": "2026-06-26T12:05:00",
    }
    with patch("api.endpoints.create_pending_action", return_value=mock_action) as mock_helper:
        resp = client.post(
            "/api/smart-home/actions",
            json={"entity_id": "light.kitchen", "service": "turn_on"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"]["id"] == 42
        assert data["action"]["status"] == "pending"
        mock_helper.assert_called_once_with(entity_id="light.kitchen", domain="light", service="turn_on")


def test_create_action_invalid_format(client: TestClient, auth_headers: dict[str, str]) -> None:
    """POST /api/smart-home/actions returns 400 bad request for malformed entity_id."""
    resp = client.post(
        "/api/smart-home/actions",
        json={"entity_id": "invalid_format_no_dot", "service": "turn_on"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "Invalid entity_id format" in resp.json()["detail"]


def test_create_action_value_error(client: TestClient, auth_headers: dict[str, str]) -> None:
    """POST /api/smart-home/actions returns 400 if domain/service validation fails."""
    with patch("api.endpoints.create_pending_action", side_effect=ValueError("Service turn_on is not permitted.")):
        resp = client.post(
            "/api/smart-home/actions",
            json={"entity_id": "light.kitchen", "service": "turn_on"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "not permitted" in resp.json()["detail"]


def test_confirm_action_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    """POST /api/smart-home/actions/{action_id}/confirm executes action successfully."""
    mock_confirm = {
        "success": True,
        "message": "turn on executed on light.kitchen.",
        "entity_id": "light.kitchen",
        "service": "turn_on",
    }
    with patch("api.endpoints.confirm_pending_action", return_value=mock_confirm) as mock_helper:
        resp = client.post("/api/smart-home/actions/42/confirm", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["entity_id"] == "light.kitchen"
        mock_helper.assert_called_once_with(42)


def test_confirm_action_value_error(client: TestClient, auth_headers: dict[str, str]) -> None:
    """POST /api/smart-home/actions/{action_id}/confirm returns 400 if action is expired/invalid."""
    with patch("api.endpoints.confirm_pending_action", side_effect=ValueError("Action #42 has expired.")):
        resp = client.post("/api/smart-home/actions/42/confirm", headers=auth_headers)
        assert resp.status_code == 400
        assert "expired" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Pet Endpoints
# ---------------------------------------------------------------------------

def test_list_pets_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    """GET /api/pets returns safe pet objects."""
    mock_pets = [
        {
            "id": 1,
            "name": "Buddy",
            "species": "dog",
            "breed": "Golden Retriever",
            "age": 4.5,
            "feeding_schedule": [],
            "last_fed": None,
            "updated_at": "2026-06-26T12:00:00",
        }
    ]
    with patch("api.endpoints.get_pets", return_value=mock_pets) as mock_helper:
        resp = client.get("/api/pets", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["pets"][0]["name"] == "Buddy"
        mock_helper.assert_called_once()


def test_feed_pet_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    """POST /api/pets/{name}/feed marks pet as fed."""
    with patch("api.endpoints.feed_pet", return_value=True) as mock_helper:
        resp = client.post("/api/pets/Buddy/feed", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["pet_name"] == "Buddy"
        mock_helper.assert_called_once_with("Buddy")


def test_feed_pet_not_found(client: TestClient, auth_headers: dict[str, str]) -> None:
    """POST /api/pets/{name}/feed returns 404 if pet name is invalid."""
    with patch("api.endpoints.feed_pet", return_value=False):
        resp = client.post("/api/pets/Ghost/feed", headers=auth_headers)
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Reminder Endpoints
# ---------------------------------------------------------------------------

def test_list_reminders_success(client: TestClient, auth_headers: dict[str, str]) -> None:
    """GET /api/reminders returns scheduled reminders."""
    mock_reminders = [
        {
            "id": "reminder-job-123",
            "name": "Feed Buddy",
            "next_run_time": "2026-06-26T18:00:00",
        }
    ]
    with patch("api.endpoints.get_scheduled_reminders", return_value=mock_reminders) as mock_helper:
        resp = client.get("/api/reminders", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 1
        assert data["reminders"][0]["id"] == "reminder-job-123"
        mock_helper.assert_called_once()


# ---------------------------------------------------------------------------
# Whitelist & Sanitizer Dependency Unit Tests
# ---------------------------------------------------------------------------

class TestSanitizerDependencies:
    """Unit tests for api/dependencies.py helper functions directly."""

    def test_safe_strip(self) -> None:
        """_safe_strip redacts sensitive credential keys recursively."""
        from api.dependencies import _safe_strip
        payload = {
            "name": "Alice",
            "password": "super-secret-password",
            "nested": {
                "token": "api-token-xyz",
                "normal": "value",
            }
        }
        res = _safe_strip(payload)
        assert res["name"] == "Alice"
        assert res["password"] == "[REDACTED]"
        assert res["nested"]["token"] == "[REDACTED]"
        assert res["nested"]["normal"] == "value"

    def test_apply_whitelist(self) -> None:
        """_apply_whitelist filters records to only allowed keys."""
        from api.dependencies import _apply_whitelist
        record = {"id": 1, "name": "Alice", "hobbies": "swimming", "notes": "notes"}
        allowed = {"name", "id"}
        res = _apply_whitelist(record, allowed)
        assert res == {"id": 1, "name": "Alice"}
