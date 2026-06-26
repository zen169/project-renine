"""Home Assistant REST API client for Renine.

Phase 7A: GET-only requests for entity state retrieval and discovery.
Phase 7B: POST requests for allowlisted service calls with confirmation gate.

Allowlisted domains (Phase 7B): light, switch, fan, cover
Allowlisted services (Phase 7B): turn_on, turn_off, toggle,
    open_cover, close_cover, stop_cover

No other domains or services may be called. All POST calls must originate
from SmartHomeAgent.execute_confirmed_action() — never called directly.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

from renine.core.config import get_settings
from renine.core.exceptions import ToolError


class HassError(ToolError):
    """Base exception for all Home Assistant client errors."""


class HassConnectionError(HassError):
    """Raised when the client fails to connect or query the Home Assistant instance."""


class HassAuthError(HassError):
    """Raised when authentication (access token validation) fails or is missing."""


class HassResponseError(HassError):
    """Raised when the Home Assistant API returns an invalid, empty, or malformed response."""


class HassServiceError(HassError):
    """Raised when an invalid or disallowed service call is attempted,
    or when the Home Assistant service endpoint returns an error."""


# Regex to validate the entity_id format (e.g. 'light.living_room' -> domain.object_id)
# Matches lowercase alphanumeric and underscores separated by a single dot.
# This conforms to Home Assistant's naming standard for entity IDs.
_ENTITY_ID_PATTERN = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")


def validate_entity_id(entity_id: str) -> None:
    """Validate that the given entity_id conforms to the Home Assistant standard format.

    Args:
        entity_id: The entity ID to validate.

    Raises:
        ValueError: If the entity ID is not a string or has an invalid format.
    """
    if not isinstance(entity_id, str):
        raise ValueError("Entity ID must be a string.")
    if not _ENTITY_ID_PATTERN.match(entity_id):
        raise ValueError(
            f"Invalid entity ID format: {entity_id!r}. Expected 'domain.object_id' format."
        )


#: Domains for which service calls are permitted in Phase 7B.
ALLOWED_DOMAINS: frozenset[str] = frozenset({"light", "switch", "fan", "cover"})

#: Services that may be called within allowed domains.
ALLOWED_SERVICES: frozenset[str] = frozenset({
    "turn_on",
    "turn_off",
    "toggle",
    "open_cover",
    "close_cover",
    "stop_cover",
})


class HassClient:
    """Read-only HTTP REST client for Home Assistant.

    Restricted entirely to HTTP GET requests. No state-changing operations
    exist in this client.
    """

    def __init__(self, base_url: str | None = None, token: str | None = None) -> None:
        """Initialize the Home Assistant REST client with a persistent httpx client.

        Args:
            base_url: The Home Assistant base URL (e.g. 'http://localhost:8123').
            token: The Long-Lived Access Token.

        Raises:
            HassAuthError: If the token is missing or empty.
        """
        settings = get_settings()
        sh_config = settings.get("smart_home", {})

        raw_base_url = base_url or sh_config.get("url", "http://localhost:8123")
        # Normalize the base URL once to remove any trailing slashes
        self.base_url = raw_base_url.rstrip("/")

        token_env = sh_config.get("token_env_var", "HASS_TOKEN")
        self.token = token or os.environ.get(token_env)

        if not self.token or not self.token.strip():
            raise HassAuthError("Home Assistant access token is missing or empty.")

        # Create persistent httpx.Client configuration
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
        }
        self._client = httpx.Client(
            base_url=self.base_url,
            headers=headers,
            timeout=httpx.Timeout(10.0),
            follow_redirects=True,
        )

    def _get(self, path: str) -> httpx.Response:
        """Execute an HTTP GET request using the persistent httpx client.

        No other HTTP verbs (POST, PUT, PATCH, DELETE) are supported.

        Args:
            path: The subpath (e.g. '/api/states').

        Returns:
            The raw httpx.Response object.

        Raises:
            HassAuthError: On 401 Unauthorized status.
            HassConnectionError: On connection failures, timeouts, or HTTP status errors.
        """
        try:
            response = self._client.get(path)

            if response.status_code == 401:
                raise HassAuthError(f"Home Assistant authentication failed (401): {response.text}")

            return response

        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise HassConnectionError(f"Failed to connect to Home Assistant: {e}")
        except httpx.TimeoutException as e:
            raise HassConnectionError(f"Home Assistant request timed out: {e}")
        except httpx.RequestError as e:
            raise HassConnectionError(f"Network request failed: {e}")

    def check_connection(self) -> bool:
        """Verify the client can connect to HA and authenticate.

        Performs a GET request to `/api/`.

        Returns:
            True if connection and authentication succeed, False otherwise.
        """
        try:
            response = self._get("/api/")
            response.raise_for_status()
            return True
        except (HassConnectionError, HassAuthError, httpx.HTTPStatusError):
            return False

    def discover_entities(self) -> list[dict[str, Any]]:
        """Retrieve state records for all discovered entities.

        Calls GET `/api/states`.

        Returns:
            A list of dictionary objects representing states.

        Raises:
            HassConnectionError: On network errors or timeouts.
            HassAuthError: On 401 Unauthorized status codes.
            HassResponseError: On empty or malformed JSON payloads.
        """
        response = self._get("/api/states")
        
        # Standardized response handling:
        # 1. 401 authentication (handled inside self._get)
        # 2. 404 (not applicable to bulk discovery)
        # 3. raise_for_status()
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HassConnectionError(f"HTTP status error occurred: {e}")

        # 4. JSON parsing with empty check and json.JSONDecodeError handling
        if not response.text or not response.text.strip():
            raise HassResponseError("Empty response payload from Home Assistant.")

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise HassResponseError(f"Failed to parse JSON response: {e}")
        except ValueError as e:
            # We catch ValueError to handle cases where legacy dependencies or older python versions
            # raise ValueError instead of JSONDecodeError during json parsing.
            raise HassResponseError(f"Failed to parse JSON: {e}")

        # 5. Payload validation
        if not isinstance(data, list):
            raise HassResponseError(
                f"Invalid response type: expected a list, got {type(data).__name__}"
            )
        return data

    def get_entity_state(self, entity_id: str) -> dict[str, Any] | None:
        """Retrieve state records for a specific entity ID.

        Calls GET `/api/states/{entity_id}`.

        Args:
            entity_id: The Home Assistant entity ID (e.g. 'light.living_room').

        Returns:
            State record dictionary, or None if the entity does not exist (404).

        Raises:
            HassConnectionError: On network errors or timeouts.
            HassAuthError: On 401 Unauthorized status codes.
            HassResponseError: On empty or malformed JSON payloads.
        """
        validate_entity_id(entity_id)

        response = self._get(f"/api/states/{entity_id}")

        # Standardized response handling:
        # 1. 401 authentication (handled inside self._get)
        # 2. 404 Check
        if response.status_code == 404:
            return None

        # 3. raise_for_status()
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HassConnectionError(f"HTTP status error occurred: {e}")

        # 4. JSON parsing with empty check and json.JSONDecodeError handling
        if not response.text or not response.text.strip():
            raise HassResponseError("Empty response payload from Home Assistant.")

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            raise HassResponseError(f"Failed to parse JSON response: {e}")
        except ValueError as e:
            # We catch ValueError to handle cases where legacy dependencies or older python versions
            # raise ValueError instead of JSONDecodeError during json parsing.
            raise HassResponseError(f"Failed to parse JSON: {e}")

        # 5. Payload validation
        if not isinstance(data, dict):
            raise HassResponseError(
                f"Invalid response type: expected a dict, got {type(data).__name__}"
            )
        return data

    def _post(self, path: str, json_body: dict[str, Any]) -> httpx.Response:
        """Execute an HTTP POST request using the persistent httpx client.

        Only used internally by call_service(). No other method may issue POST.

        Args:
            path: The subpath (e.g. '/api/services/light/turn_on').
            json_body: JSON-serialisable request body.

        Returns:
            The raw httpx.Response object.

        Raises:
            HassAuthError: On 401 Unauthorized status.
            HassConnectionError: On connection failures, timeouts, or other HTTP errors.
        """
        try:
            response = self._client.post(path, json=json_body)

            if response.status_code == 401:
                raise HassAuthError(
                    f"Home Assistant authentication failed (401): {response.text}"
                )

            return response

        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise HassConnectionError(f"Failed to connect to Home Assistant: {e}")
        except httpx.TimeoutException as e:
            raise HassConnectionError(f"Home Assistant request timed out: {e}")
        except httpx.RequestError as e:
            raise HassConnectionError(f"Network request failed: {e}")

    def call_service(
        self,
        domain: str,
        service: str,
        entity_id: str,
        service_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call a Home Assistant service for the given entity.

        PHASE 7B ONLY. Validates domain and service against the configured
        allowlists before issuing any network call. Raises HassServiceError
        immediately if the combination is not permitted.

        Allowed domains: light, switch, fan, cover
        Allowed services: turn_on, turn_off, toggle, open_cover, close_cover, stop_cover

        Args:
            domain: HA domain (e.g. 'light', 'switch').
            service: HA service name (e.g. 'turn_on', 'turn_off').
            entity_id: Target entity ID (e.g. 'light.living_room').
            service_data: Optional extra payload merged into the service call body.

        Returns:
            Parsed JSON response from Home Assistant (list or dict).

        Raises:
            HassServiceError: If domain or service is not in the allowlist,
                or if the API returns a non-success status.
            HassAuthError: On 401 Unauthorized.
            HassConnectionError: On network failures or timeouts.
            HassResponseError: On malformed JSON response.
            ValueError: If entity_id format is invalid.
        """
        # 1. Allowlist validation — no network call if invalid
        if domain not in ALLOWED_DOMAINS:
            raise HassServiceError(
                f"Domain '{domain}' is not in the allowed list: {sorted(ALLOWED_DOMAINS)}"
            )
        if service not in ALLOWED_SERVICES:
            raise HassServiceError(
                f"Service '{service}' is not in the allowed list: {sorted(ALLOWED_SERVICES)}"
            )

        # 2. Entity ID format validation
        validate_entity_id(entity_id)

        # 3. Build request body
        body: dict[str, Any] = {"entity_id": entity_id}
        if service_data:
            body.update(service_data)

        # 4. POST /api/services/{domain}/{service}
        path = f"/api/services/{domain}/{service}"
        response = self._post(path, body)

        # 5. Check for non-success status
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HassServiceError(
                f"Service call {domain}.{service} failed with HTTP {response.status_code}: {e}"
            )

        # 6. Parse and return response (HA returns [] for success with no state change,
        #    or a list of affected states)
        if not response.text or not response.text.strip():
            # Empty body is acceptable for some service calls
            return {}

        try:
            data = response.json()
        except (json.JSONDecodeError, ValueError) as e:
            raise HassResponseError(f"Failed to parse service call response: {e}")

        return data if isinstance(data, dict) else {"result": data}

    def close(self) -> None:
        """Close the underlying persistent HTTP client."""
        self._client.close()

    def __enter__(self) -> HassClient:
        """Enter the context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit the context manager and clean up resources."""
        self.close()
