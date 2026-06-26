"""JWT authentication utilities and dependency injection for Renine Mobile API."""
from __future__ import annotations

import datetime
from typing import Any
import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from renine.core.config import get_settings
from renine.core.logging_config import get_logger

logger = get_logger(__name__)

# OAuth2 scheme for extracting Bearer tokens from request headers
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash.

    Args:
        plain_password: Plain text password input.
        hashed_password: Hashed password string from storage/config.

    Returns:
        True if the password matches, False otherwise.
    """
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception as e:
        logger.error("password_verification_failed", error=str(e))
        return False


def get_password_hash(password: str) -> str:
    """Generate a bcrypt hash for a plain-text password.

    Args:
        password: Plain text password string.

    Returns:
        The hashed password string.
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def create_access_token(data: dict[str, Any], expires_delta: datetime.timedelta | None = None) -> str:
    """Create a signed JWT access token.

    Args:
        data: Key-value claims to include in the token payload.
        expires_delta: Optional custom duration before expiration.

    Returns:
        Encoded JWT token string.
    """
    settings = get_settings()
    api_cfg = settings.get("api", {})
    secret_key = api_cfg.get("jwt_secret", "super-secret-renine-jwt-key")
    algorithm = "HS256"

    to_encode = data.copy()
    if expires_delta:
        expire = datetime.datetime.now(datetime.timezone.utc) + expires_delta
    else:
        minutes = api_cfg.get("jwt_expire_minutes", 60)
        expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, secret_key, algorithm=algorithm)
    return encoded_jwt


def verify_token(token: str) -> dict[str, Any] | None:
    """Verify and decode a JWT token.

    Args:
        token: Signed JWT token string.

    Returns:
        Decoded payload dictionary if valid, None otherwise.
    """
    settings = get_settings()
    api_cfg = settings.get("api", {})
    secret_key = api_cfg.get("jwt_secret", "super-secret-renine-jwt-key")
    algorithm = "HS256"

    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        return payload
    except jwt.PyJWTError as e:
        logger.warning("token_verification_failed", error=str(e))
        return None


def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """FastAPI dependency to retrieve the currently authenticated user.

    Args:
        token: Extracted bearer token.

    Returns:
        Authenticated username string.

    Raises:
        HTTPException: If credentials validation fails.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = verify_token(token)
    if payload is None:
        raise credentials_exception

    username: str | None = payload.get("sub")
    if username is None:
        raise credentials_exception

    return username
