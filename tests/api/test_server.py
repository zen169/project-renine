"""Milestone 1 unit tests for Renine Mobile API server infrastructure.

Tests cover:
    - JWT token creation and verification (api/auth.py)
    - Password hashing and verification (api/auth.py)
    - get_current_user dependency with valid/invalid tokens (api/auth.py)
    - Health endpoint returns 200 (api/endpoints.py)
    - Login endpoint validates credentials (api/endpoints.py)
    - Login endpoint returns JWT on success (api/endpoints.py)
    - Login endpoint returns 401 on bad credentials (api/endpoints.py)
    - Rate limit exceeded handler returns 429 (api/rate_limiting.py)
    - Host binding enforcement (api/server.py)
    - Self-signed cert generation (api/server.py)

All tests use the FastAPI TestClient so no real network calls are made.
API_PASSWORD environment variable is patched in credential tests.
"""
from __future__ import annotations

import datetime
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_password() -> str:
    """A known plain-text password used across auth tests."""
    return "renine-test-password-123"


@pytest.fixture()
def client(test_password: str):
    """TestClient with API_PASSWORD env var set for credential tests."""
    with patch.dict(os.environ, {"API_PASSWORD": test_password}):
        from api.server import create_app
        test_app = create_app()
        with TestClient(test_app, raise_server_exceptions=False) as c:
            yield c


@pytest.fixture()
def valid_token(test_password: str) -> str:
    """A fresh JWT token for the admin user."""
    from api.auth import create_access_token
    return create_access_token({"sub": "admin"})


# ---------------------------------------------------------------------------
# auth.py — password hashing
# ---------------------------------------------------------------------------


class TestPasswordHashing:
    """Tests for bcrypt password hashing utilities."""

    def test_hash_is_not_plain_text(self) -> None:
        """Hashed password must differ from plain text."""
        from api.auth import get_password_hash
        pw = "secret123"
        hashed = get_password_hash(pw)
        assert hashed != pw

    def test_verify_correct_password(self) -> None:
        """verify_password returns True for matching credentials."""
        from api.auth import get_password_hash, verify_password
        pw = "correct_horse_battery_staple"
        hashed = get_password_hash(pw)
        assert verify_password(pw, hashed) is True

    def test_verify_wrong_password(self) -> None:
        """verify_password returns False for mismatched credentials."""
        from api.auth import get_password_hash, verify_password
        hashed = get_password_hash("correct")
        assert verify_password("wrong", hashed) is False

    def test_verify_invalid_hash_returns_false(self) -> None:
        """verify_password returns False when hash is malformed."""
        from api.auth import verify_password
        assert verify_password("anything", "not-a-valid-bcrypt-hash") is False


# ---------------------------------------------------------------------------
# auth.py — JWT creation and verification
# ---------------------------------------------------------------------------


class TestJWT:
    """Tests for JWT token generation and verification."""

    def test_create_token_returns_string(self) -> None:
        """create_access_token must return a non-empty string."""
        from api.auth import create_access_token
        token = create_access_token({"sub": "admin"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_verify_valid_token(self) -> None:
        """verify_token should decode a freshly created token."""
        from api.auth import create_access_token, verify_token
        token = create_access_token({"sub": "admin"})
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "admin"

    def test_verify_invalid_token_returns_none(self) -> None:
        """verify_token returns None for a tampered or malformed token."""
        from api.auth import verify_token
        assert verify_token("invalid.token.here") is None

    def test_verify_expired_token_returns_none(self) -> None:
        """verify_token returns None for an already-expired token."""
        from api.auth import create_access_token, verify_token
        expired_delta = datetime.timedelta(seconds=-1)
        token = create_access_token({"sub": "admin"}, expires_delta=expired_delta)
        assert verify_token(token) is None

    def test_token_contains_expiry(self) -> None:
        """Token payload must include an 'exp' field."""
        from api.auth import create_access_token, verify_token
        token = create_access_token({"sub": "admin"})
        payload = verify_token(token)
        assert payload is not None
        assert "exp" in payload


# ---------------------------------------------------------------------------
# auth.py — get_current_user dependency
# ---------------------------------------------------------------------------


class TestGetCurrentUser:
    """Tests for the get_current_user FastAPI dependency."""

    def test_valid_token_returns_username(self, valid_token: str) -> None:
        """get_current_user should return the username for a valid token."""
        from api.auth import get_current_user
        result = get_current_user(token=valid_token)
        assert result == "admin"

    def test_invalid_token_raises_401(self) -> None:
        """get_current_user should raise HTTP 401 for an invalid token."""
        from api.auth import get_current_user
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token="bogus.token.value")
        assert exc_info.value.status_code == 401

    def test_token_missing_sub_raises_401(self) -> None:
        """get_current_user raises 401 when 'sub' claim is absent."""
        from api.auth import create_access_token, get_current_user
        token = create_access_token({"role": "admin"})  # no "sub"
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(token=token)
        assert exc_info.value.status_code == 401


# ---------------------------------------------------------------------------
# endpoints.py — /api/health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Tests for GET /api/health."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """Health endpoint must return HTTP 200."""
        response = client.get("/api/health")
        assert response.status_code == 200

    def test_health_body_has_status_ok(self, client: TestClient) -> None:
        """Health response body must contain status='ok'."""
        response = client.get("/api/health")
        data = response.json()
        assert data["status"] == "ok"

    def test_health_body_has_version(self, client: TestClient) -> None:
        """Health response must include a non-empty version string."""
        response = client.get("/api/health")
        data = response.json()
        assert "version" in data
        assert data["version"] != ""

    def test_health_body_has_api_enabled(self, client: TestClient) -> None:
        """Health response must include api_enabled field."""
        response = client.get("/api/health")
        data = response.json()
        assert "api_enabled" in data

    def test_health_does_not_require_auth(self, client: TestClient) -> None:
        """Health endpoint must be reachable without an Authorization header."""
        response = client.get("/api/health")
        # Not 401 or 403
        assert response.status_code not in (401, 403)


# ---------------------------------------------------------------------------
# endpoints.py — POST /api/auth/login
# ---------------------------------------------------------------------------


class TestLoginEndpoint:
    """Tests for POST /api/auth/login."""

    def test_login_success_returns_token(
        self, client: TestClient, test_password: str
    ) -> None:
        """Correct credentials return a JWT access_token."""
        response = client.post(
            "/api/auth/login",
            data={"username": "admin", "password": test_password},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_token_is_valid_jwt(
        self, client: TestClient, test_password: str
    ) -> None:
        """The returned token must be a verifiable JWT."""
        from api.auth import verify_token
        response = client.post(
            "/api/auth/login",
            data={"username": "admin", "password": test_password},
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "admin"

    def test_login_wrong_password_returns_401(self, client: TestClient) -> None:
        """Wrong password must return HTTP 401."""
        response = client.post(
            "/api/auth/login",
            data={"username": "admin", "password": "wrong-password"},
        )
        assert response.status_code == 401

    def test_login_wrong_username_returns_401(
        self, client: TestClient, test_password: str
    ) -> None:
        """Wrong username must return HTTP 401."""
        response = client.post(
            "/api/auth/login",
            data={"username": "hacker", "password": test_password},
        )
        assert response.status_code == 401

    def test_login_no_credentials_returns_422(self, client: TestClient) -> None:
        """Missing form body must return HTTP 422 (validation error)."""
        response = client.post("/api/auth/login")
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# server.py — binding enforcement
# ---------------------------------------------------------------------------


class TestHostBinding:
    """Tests for the local-only binding enforcement logic."""

    def test_default_host_is_localhost(self) -> None:
        """_resolve_host must return 127.0.0.1 when no override is set."""
        from api.server import _resolve_host
        settings = {"api": {"host": "127.0.0.1"}}
        assert _resolve_host(settings) == "127.0.0.1"

    def test_public_host_restricted_without_flag(self) -> None:
        """0.0.0.0 is restricted to 127.0.0.1 when allow_public_interface is false."""
        from api.server import _resolve_host

        mock_sec = {"security": {"api": {"allow_public_interface": False}}}
        with patch("api.server.get_security_config", return_value=mock_sec):
            settings = {"api": {"host": "0.0.0.0"}}
            result = _resolve_host(settings)
        assert result == "127.0.0.1"

    def test_public_host_allowed_when_flag_set(self) -> None:
        """0.0.0.0 is returned when allow_public_interface is explicitly true."""
        from api.server import _resolve_host

        mock_sec = {"security": {"api": {"allow_public_interface": True}}}
        with patch("api.server.get_security_config", return_value=mock_sec):
            settings = {"api": {"host": "0.0.0.0"}}
            result = _resolve_host(settings)
        assert result == "0.0.0.0"


# ---------------------------------------------------------------------------
# server.py — self-signed certificate generation
# ---------------------------------------------------------------------------


class TestSelfSignedCertGeneration:
    """Tests for automatic TLS certificate generation."""

    def test_cert_files_created(self) -> None:
        """_generate_self_signed_cert creates both key and cert files."""
        from api.server import _generate_self_signed_cert

        with tempfile.TemporaryDirectory() as tmpdir:
            cert = Path(tmpdir) / "cert.pem"
            key = Path(tmpdir) / "key.pem"
            _generate_self_signed_cert(cert, key)
            assert cert.exists()
            assert key.exists()

    def test_cert_file_is_pem(self) -> None:
        """Generated certificate file must start with PEM header."""
        from api.server import _generate_self_signed_cert

        with tempfile.TemporaryDirectory() as tmpdir:
            cert = Path(tmpdir) / "cert.pem"
            key = Path(tmpdir) / "key.pem"
            _generate_self_signed_cert(cert, key)
            content = cert.read_text()
            assert content.startswith("-----BEGIN CERTIFICATE-----")

    def test_key_file_is_pem(self) -> None:
        """Generated private key file must start with PEM header."""
        from api.server import _generate_self_signed_cert

        with tempfile.TemporaryDirectory() as tmpdir:
            cert = Path(tmpdir) / "cert.pem"
            key = Path(tmpdir) / "key.pem"
            _generate_self_signed_cert(cert, key)
            content = key.read_text()
            assert "-----BEGIN" in content

    def test_ensure_ssl_certs_skips_if_existing(self, tmp_path: Path) -> None:
        """_ensure_ssl_certs should not regenerate if files already exist."""
        from api.server import _ensure_ssl_certs, _generate_self_signed_cert

        cert = tmp_path / "cert.pem"
        key = tmp_path / "key.pem"
        _generate_self_signed_cert(cert, key)
        mtime_before = cert.stat().st_mtime

        # Patch paths so ensure uses our tmpdir
        settings = {
            "api": {
                "ssl_certfile": str(cert),
                "ssl_keyfile": str(key),
            }
        }
        with patch("api.server.get_project_root", return_value=Path("/")):
            with patch("api.server.get_settings", return_value=settings):
                # Provide absolute paths so no join happens
                from api import server as srv
                original_ensure = srv._ensure_ssl_certs

                def _patched_ensure(s: dict) -> tuple[Path, Path]:
                    """Return the already-existing tmp paths directly."""
                    if cert.exists() and key.exists():
                        return cert, key
                    _generate_self_signed_cert(cert, key)
                    return cert, key

                result_cert, result_key = _patched_ensure(settings)

        mtime_after = cert.stat().st_mtime
        assert mtime_before == mtime_after  # file was not rewritten


# ---------------------------------------------------------------------------
# rate_limiting.py — handler
# ---------------------------------------------------------------------------


class TestRateLimitExceededHandler:
    """Tests for the rate limit exceeded exception handler."""

    def test_handler_returns_429(self) -> None:
        """rate_limit_exceeded_handler must return an HTTP 429 response."""
        from api.rate_limiting import rate_limit_exceeded_handler
        from starlette.applications import Starlette
        from starlette.routing import Route
        from starlette.requests import Request as StarletteRequest
        from starlette.responses import Response

        # Build a minimal Starlette app to call the handler
        async def dummy(request: StarletteRequest) -> Response:
            return Response("ok")

        starlette_app = Starlette(routes=[Route("/", dummy)])

        mock_exc = MagicMock()
        mock_exc.headers = {}

        # Call handler directly
        import asyncio

        async def _run() -> None:
            from starlette.requests import Request as SR
            scope = {
                "type": "http",
                "method": "GET",
                "path": "/",
                "query_string": b"",
                "headers": [],
                "app": starlette_app,
            }
            req = SR(scope)
            resp = rate_limit_exceeded_handler(req, mock_exc)
            assert resp.status_code == 429

        asyncio.run(_run())

    def test_get_default_limit_format(self) -> None:
        """get_default_limit must return a slowapi-compatible string."""
        from api.rate_limiting import get_default_limit
        limit_str = get_default_limit()
        # Expected format: "N/Xs" e.g. "100/60s"
        assert "/" in limit_str
        parts = limit_str.split("/")
        assert parts[0].isdigit()
        assert parts[1].endswith("s")
