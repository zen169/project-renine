"""Rate limiting middleware for Renine Mobile API using slowapi."""
from __future__ import annotations

from fastapi import Request, Response
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from renine.core.config import get_settings


def get_default_limit() -> str:
    """Retrieve the rate limit rule string from settings.yaml.

    Returns:
        Formatted rate limit string (e.g. "100/60s" or "100/minute").
    """
    settings = get_settings()
    api_cfg = settings.get("api", {})
    limit = api_cfg.get("rate_limit_limit", 100)
    period = api_cfg.get("rate_limit_period_seconds", 60)
    return f"{limit}/{period}s"


# Initialize the rate limiter with client IP address as key
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[get_default_limit],
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> Response:
    """Custom response handler for rate limit exceeded errors.

    Args:
        request: The incoming FastAPI request object.
        exc: The exception instance raised.

    Returns:
        JSON response with 429 status code.
    """
    from fastapi.responses import JSONResponse

    response = JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Rate limit exceeded."},
    )
    # Re-apply headers from slowapi
    response.headers.update(getattr(exc, "headers", {}))
    return response
