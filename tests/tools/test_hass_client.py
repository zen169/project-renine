"""Unit tests for the read-only Home Assistant REST API client."""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

from renine.tools.smart_home.hass_client import (
    HassAuthError,
    HassClient,
    HassConnectionError,
    HassResponseError,
    HassServiceError,
    validate_entity_id,
)


class TestHassClient:
    """Test suite for HassClient operations and error handling."""

    def test_hass_client_get_only_enforcement(self) -> None:
        """Verify that HassClient has no POST/PUT/PATCH/DELETE methods and GET is enforced."""
        client = HassClient(base_url="http://localhost:8123", token="mock_token")

        # Confirm no state-changing method names exist on the class or client instance
        forbidden_methods = ["post", "put", "patch", "delete", "request"]
        for method in forbidden_methods:
            assert not hasattr(client, method)
            assert not hasattr(HassClient, method)

        # Check the underlying requests to prove only GET is called
        with patch.object(client._client, "get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = '{"message": "API running."}'
            mock_response.json.return_value = {"message": "API running."}
            mock_get.return_value = mock_response

            client.check_connection()

            # Assert client._client.get was called (GET-only request method)
            mock_get.assert_called_once()
            called_path = mock_get.call_args[0][0]
            assert "/api/" in called_path
            assert "services" not in called_path

    def test_base_url_trailing_slash_removed(self) -> None:
        """Verify trailing slashes are normalized from the base URL during init."""
        client = HassClient(base_url="http://localhost:8123/", token="mock_token")
        assert client.base_url == "http://localhost:8123"

        client_double_slash = HassClient(base_url="http://localhost:8123//", token="mock_token")
        assert client_double_slash.base_url == "http://localhost:8123"

    def test_client_cleanup_close(self) -> None:
        """Verify close method closes the underlying httpx client."""
        client = HassClient(base_url="http://localhost:8123", token="mock_token")
        with patch.object(client._client, "close") as mock_close:
            client.close()
            mock_close.assert_called_once()

    def test_client_context_manager(self) -> None:
        """Verify that context manager correctly opens and cleans up the client."""
        with patch("httpx.Client.close") as mock_close:
            with HassClient(base_url="http://localhost:8123", token="mock_token") as client:
                assert isinstance(client, HassClient)
            mock_close.assert_called_once()

    def test_missing_or_empty_token_raises_auth_error(self) -> None:
        """HassClient constructor raises HassAuthError when token is missing or empty."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("renine.tools.smart_home.hass_client.get_settings", return_value={}):
                with pytest.raises(HassAuthError) as exc_info:
                    HassClient(base_url="http://localhost:8123", token=None)
                assert "access token is missing or empty" in str(exc_info.value)

                with pytest.raises(HassAuthError):
                    HassClient(base_url="http://localhost:8123", token="   ")

    def test_connection_timeout_raises_connection_error(self) -> None:
        """httpx timeout exceptions are mapped to HassConnectionError."""
        client = HassClient(base_url="http://localhost:8123", token="mock_token")

        with patch.object(client._client, "get", side_effect=httpx.TimeoutException("Timeout occurred")):
            with pytest.raises(HassConnectionError) as exc_info:
                client.discover_entities()
            assert "request timed out" in str(exc_info.value).lower()

        with patch.object(client._client, "get", side_effect=httpx.ConnectTimeout("Connect timeout")):
            with pytest.raises(HassConnectionError) as exc_info:
                client.discover_entities()
            assert "failed to connect" in str(exc_info.value).lower()

    def test_authentication_failure_401_raises_auth_error(self) -> None:
        """HASS 401 response status raises HassAuthError."""
        client = HassClient(base_url="http://localhost:8123", token="mock_token")
        
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch.object(client._client, "get", return_value=mock_response):
            with pytest.raises(HassAuthError) as exc_info:
                client.discover_entities()
            assert "authentication failed" in str(exc_info.value).lower()

    def test_get_entity_state_returns_none_on_404(self) -> None:
        """get_entity_state returns None when Home Assistant reports 404 Not Found."""
        client = HassClient(base_url="http://localhost:8123", token="mock_token")

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"

        with patch.object(client._client, "get", return_value=mock_response):
            result = client.get_entity_state("light.nonexistent_device")
            assert result is None

    def test_invalid_json_payload_raises_response_error(self) -> None:
        """Malformed JSON payload raises HassResponseError (catching JSONDecodeError)."""
        client = HassClient(base_url="http://localhost:8123", token="mock_token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "invalid json payload"
        # Simulate JSON parsing exception
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "doc", 0)

        with patch.object(client._client, "get", return_value=mock_response):
            with pytest.raises(HassResponseError) as exc_info:
                client.discover_entities()
            assert "failed to parse json" in str(exc_info.value).lower()

    def test_empty_payload_raises_response_error(self) -> None:
        """Empty or whitespace-only response payload raises HassResponseError."""
        client = HassClient(base_url="http://localhost:8123", token="mock_token")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "   "

        with patch.object(client._client, "get", return_value=mock_response):
            with pytest.raises(HassResponseError) as exc_info:
                client.discover_entities()
            assert "empty response payload" in str(exc_info.value).lower()

    def test_entity_id_validation_prevents_request(self) -> None:
        """Invalid entity_id format raises ValueError before making any HTTP request."""
        client = HassClient(base_url="http://localhost:8123", token="mock_token")

        invalid_ids = [
            "light",
            "light.",
            ".light",
            "light.kitchen.lamp",
            "light/kitchen",
            "light.kitchen!",
            123,
            None,
        ]

        with patch.object(client._client, "get") as mock_get:
            for invalid_id in invalid_ids:
                with pytest.raises(ValueError):
                    client.get_entity_state(invalid_id)  # type: ignore

            # Assert no requests were ever sent
            mock_get.assert_not_called()

    def test_discover_entities_success(self) -> None:
        """discover_entities successfully returns a parsed list of states."""
        client = HassClient(base_url="http://localhost:8123", token="mock_token")
        
        mock_payload = [
            {"entity_id": "light.living_room", "state": "on"},
            {"entity_id": "sensor.temperature", "state": "21.5"},
        ]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '[{"entity_id": "light.living_room", "state": "on"}]'
        mock_response.json.return_value = mock_payload

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            entities = client.discover_entities()
            assert len(entities) == 2
            assert entities[0]["entity_id"] == "light.living_room"
            mock_get.assert_called_once_with("/api/states")

    def test_check_connection_success(self) -> None:
        """Verify check_connection returns True when GET to /api/ succeeds with 200 OK."""
        client = HassClient(base_url="http://localhost:8123", token="mock_token")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        with patch.object(client._client, "get", return_value=mock_response):
            assert client.check_connection() is True

    def test_check_connection_failure(self) -> None:
        """Verify check_connection catches connection/auth issues and returns False."""
        client = HassClient(base_url="http://localhost:8123", token="mock_token")
        
        # 1. 401 Unauthorized
        mock_response_401 = MagicMock()
        mock_response_401.status_code = 401
        mock_response_401.text = "Unauthorized"
        
        with patch.object(client._client, "get", return_value=mock_response_401):
            assert client.check_connection() is False

        # 2. Connection Timeout
        with patch.object(client._client, "get", side_effect=httpx.ConnectTimeout("timeout")):
            assert client.check_connection() is False

        # 3. HTTP status error (e.g. 500 Server Error)
        mock_response_500 = MagicMock()
        mock_response_500.status_code = 500
        mock_response_500.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Internal Server Error", request=MagicMock(), response=mock_response_500
        )
        with patch.object(client._client, "get", return_value=mock_response_500):
            assert client.check_connection() is False

    def test_discover_entities_non_list_payload(self) -> None:
        """discover_entities raises HassResponseError if payload JSON is not a list."""
        client = HassClient(base_url="http://localhost:8123", token="mock_token")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '{"error": "bad type"}'
        mock_response.json.return_value = {"error": "bad type"}

        with patch.object(client._client, "get", return_value=mock_response):
            with pytest.raises(HassResponseError) as exc_info:
                client.discover_entities()
            assert "invalid response type" in str(exc_info.value).lower()

    def test_get_entity_state_non_dict_payload(self) -> None:
        """get_entity_state raises HassResponseError if payload JSON is not a dict."""
        client = HassClient(base_url="http://localhost:8123", token="mock_token")
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '["state1", "state2"]'
        mock_response.json.return_value = ["state1", "state2"]

        with patch.object(client._client, "get", return_value=mock_response):
            with pytest.raises(HassResponseError) as exc_info:
                client.get_entity_state("light.living_room")
            assert "invalid response type" in str(exc_info.value).lower()


class TestEntityIdValidation:
    """Tests for the helper utility validate_entity_id."""

    def test_valid_entity_ids(self) -> None:
        """Valid entity ID formats pass silently."""
        validate_entity_id("light.living_room")
        validate_entity_id("sensor.bedroom_temp")
        validate_entity_id("binary_sensor.front_door")

    def test_invalid_entity_ids(self) -> None:
        """Invalid entity ID formats raise ValueError."""
        with pytest.raises(ValueError):
            validate_entity_id("light")
        with pytest.raises(ValueError):
            validate_entity_id("light.living.room")
        with pytest.raises(ValueError):
            validate_entity_id("light.")
        with pytest.raises(ValueError):
            validate_entity_id(".light")


class TestHassClientCallService:
    """Test suite for HassClient.call_service() allowlisting and execution."""

    def test_call_service_success(self) -> None:
        """Verify successful call_service execution with allowlisted parameters."""
        client = HassClient(base_url="http://localhost:8123", token="mock_token")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = '[{"entity_id": "light.living_room", "state": "on"}]'
        mock_response.json.return_value = [{"entity_id": "light.living_room", "state": "on"}]

        with patch.object(client._client, "post", return_value=mock_response) as mock_post:
            res = client.call_service("light", "turn_on", "light.living_room", {"brightness": 255})
            assert res == {"result": [{"entity_id": "light.living_room", "state": "on"}]}
            mock_post.assert_called_once_with(
                "/api/services/light/turn_on",
                json={"entity_id": "light.living_room", "brightness": 255}
            )

    def test_call_service_disallowed_domain_raises(self) -> None:
        """Verify disallowed domain raises HassServiceError without network call."""
        client = HassClient(base_url="http://localhost:8123", token="mock_token")
        with patch.object(client._client, "post") as mock_post:
            with pytest.raises(HassServiceError) as exc_info:
                client.call_service("climate", "turn_on", "climate.living_room")
            assert "domain 'climate' is not in the allowed list" in str(exc_info.value).lower()
            mock_post.assert_not_called()

    def test_call_service_disallowed_service_raises(self) -> None:
        """Verify disallowed service raises HassServiceError without network call."""
        client = HassClient(base_url="http://localhost:8123", token="mock_token")
        with patch.object(client._client, "post") as mock_post:
            with pytest.raises(HassServiceError) as exc_info:
                client.call_service("light", "flash", "light.living_room")
            assert "service 'flash' is not in the allowed list" in str(exc_info.value).lower()
            mock_post.assert_not_called()

    def test_call_service_invalid_entity_id_raises(self) -> None:
        """Verify invalid entity_id format raises ValueError without network call."""
        client = HassClient(base_url="http://localhost:8123", token="mock_token")
        with patch.object(client._client, "post") as mock_post:
            with pytest.raises(ValueError):
                client.call_service("light", "turn_on", "invalid_id")
            mock_post.assert_not_called()

    def test_call_service_non_success_status_raises(self) -> None:
        """Verify non-success HTTP status from HA raises HassServiceError."""
        client = HassClient(base_url="http://localhost:8123", token="mock_token")
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        # mock httpx status error raising
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )

        with patch.object(client._client, "post", return_value=mock_response):
            with pytest.raises(HassServiceError) as exc_info:
                client.call_service("light", "turn_on", "light.living_room")
            assert "failed with http 500" in str(exc_info.value).lower()

    def test_call_service_auth_failure_raises(self) -> None:
        """Verify 401 Unauthorized raises HassAuthError."""
        client = HassClient(base_url="http://localhost:8123", token="mock_token")
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch.object(client._client, "post", return_value=mock_response):
            with pytest.raises(HassAuthError) as exc_info:
                client.call_service("light", "turn_on", "light.living_room")
            assert "authentication failed" in str(exc_info.value).lower()

    def test_call_service_malformed_json_raises(self) -> None:
        """Verify malformed JSON response raises HassResponseError."""
        client = HassClient(base_url="http://localhost:8123", token="mock_token")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "not json"
        mock_response.json.side_effect = json.JSONDecodeError("Expecting value", "doc", 0)

        with patch.object(client._client, "post", return_value=mock_response):
            with pytest.raises(HassResponseError) as exc_info:
                client.call_service("light", "turn_on", "light.living_room")
            assert "failed to parse" in str(exc_info.value).lower()
