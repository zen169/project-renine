"""Renine Mobile API — route definitions.

Milestone 1 routes:
    POST /api/auth/login   — Exchange username + password for a JWT token.
    GET  /api/health       — Unauthenticated health check (server liveness probe).

All data-access routes (Milestone 2) will be added to this file.
"""
from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from renine.core.config import get_settings
from renine.core.logging_config import get_logger
from api.auth import create_access_token, get_current_user, get_password_hash, verify_password
from api.rate_limiting import limiter

logger = get_logger(__name__)

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class TokenResponse(BaseModel):
    """Response schema for successful authentication."""

    access_token: str
    token_type: str


class HealthResponse(BaseModel):
    """Response schema for health check."""

    status: str
    version: str
    api_enabled: bool


# ---------------------------------------------------------------------------
# Helper: validate credentials against config
# ---------------------------------------------------------------------------

def _authenticate_user(username: str, password: str) -> bool:
    """Validate username and password against config/settings.yaml values.

    The password stored in settings is an API_PASSWORD env-var.  If the env
    var is not set we fall back to a bcrypt-hashed default stored in the config.
    Because bcrypt salts are unique, the comparison is safe even in tests.

    Args:
        username: Provided username string.
        password: Provided plain-text password string.

    Returns:
        True if credentials are valid, False otherwise.
    """
    settings = get_settings()
    api_cfg = settings.get("api", {})
    expected_username = api_cfg.get("username", "admin")

    # Password comes from environment variable API_PASSWORD; fall back to
    # a hashed version stored under api.password_hash if present.
    plain_env = os.environ.get("API_PASSWORD", "")
    hashed_cfg = api_cfg.get("password_hash", "")

    if username != expected_username:
        logger.warning("auth_failed_unknown_user", username=username)
        return False

    # Priority 1: direct env-var comparison (plain text in env, OK for local use)
    if plain_env:
        return password == plain_env

    # Priority 2: bcrypt hash stored in config
    if hashed_cfg:
        return verify_password(password, hashed_cfg)

    # Priority 3: no password configured → deny all
    logger.warning("auth_no_password_configured")
    return False


# ---------------------------------------------------------------------------
# POST /api/auth/login
# ---------------------------------------------------------------------------

@router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="Authenticate and receive a JWT access token",
)
@limiter.limit("10/minute")
async def login(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> TokenResponse:
    """Authenticate with username and password; return a JWT access token.

    Args:
        request: FastAPI request (required by SlowAPI limiter).
        form_data: OAuth2 form data (username + password).

    Returns:
        TokenResponse with access_token and token_type.

    Raises:
        HTTPException 401: If credentials are incorrect.
    """
    if not _authenticate_user(form_data.username, form_data.password):
        logger.warning("login_failed", username=form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(data={"sub": form_data.username})
    logger.info("login_success", username=form_data.username)
    return TokenResponse(access_token=token, token_type="bearer")


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness health check",
)
@limiter.limit("60/minute")
async def health(request: Request) -> HealthResponse:
    """Return basic server health information.

    This endpoint is intentionally unauthenticated so that monitoring tools
    and the mobile app can detect server availability before logging in.

    Args:
        request: FastAPI request (required by SlowAPI limiter).

    Returns:
        HealthResponse with status, version, and api_enabled flag.
    """
    settings = get_settings()
    version = settings.get("app", {}).get("version", "unknown")
    api_enabled = settings.get("features", {}).get("api_enabled", True)

    return HealthResponse(
        status="ok",
        version=version,
        api_enabled=api_enabled,
    )
