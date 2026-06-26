"""FastAPI server for Renine Mobile Companion API.

Security rules enforced here:
  1. Binds to 127.0.0.1 by default; binds to 0.0.0.0 ONLY if
     security.api.allow_public_interface is explicitly set to true.
  2. Self-signed TLS certificate is auto-generated if not present.
  3. All endpoints require JWT authentication (see api/auth.py).
  4. SlowAPI rate limiting is applied to every route.
  5. All responses are passed through ContextSanitizer.

Inputs:
    - config/settings.yaml  — API host, port, cert paths, credentials
    - config/security.yaml  — interface binding flag, field whitelists

Outputs:
    - Uvicorn HTTPS server on the configured local interface.

Entry point:
    python -m api.server
"""
from __future__ import annotations

import contextlib
import os
import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from renine.core.config import get_project_root, get_security_config, get_settings
from renine.core.exceptions import RenineError
from renine.core.logging_config import get_logger
from api.rate_limiting import limiter, rate_limit_exceeded_handler

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helper: self-signed TLS certificate generation
# ---------------------------------------------------------------------------

def _generate_self_signed_cert(cert_path: Path, key_path: Path) -> None:
    """Generate a self-signed TLS certificate and private key using cryptography.

    Creates parent directories as required. Certificate is valid for 365 days
    and issued to 'renine.local'.

    Args:
        cert_path: Destination path for the PEM certificate file.
        key_path: Destination path for the PEM private key file.
    """
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    cert_path.parent.mkdir(parents=True, exist_ok=True)

    # Generate RSA private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Build certificate subject and issuer
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "renine.local"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Renine"),
    ])

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(
            datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(days=365)
        )
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("renine.local"),
                x509.DNSName("localhost"),
            ]),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    # Write private key
    key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

    # Write certificate
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    logger.info(
        "ssl_cert_generated",
        cert=str(cert_path),
        key=str(key_path),
    )


def _ensure_ssl_certs(settings: dict[str, Any]) -> tuple[Path, Path]:
    """Ensure that TLS certificate files exist, generating them if absent.

    Args:
        settings: Parsed settings dictionary from settings.yaml.

    Returns:
        Tuple of (cert_path, key_path) as resolved Path objects.
    """
    root = get_project_root()
    api_cfg = settings.get("api", {})

    cert_rel = api_cfg.get("ssl_certfile", "config/certs/cert.pem")
    key_rel = api_cfg.get("ssl_keyfile", "config/certs/key.pem")

    cert_path = (root / cert_rel).resolve()
    key_path = (root / key_rel).resolve()

    if not cert_path.exists() or not key_path.exists():
        logger.info("ssl_certs_missing_generating")
        _generate_self_signed_cert(cert_path, key_path)
    else:
        logger.info("ssl_certs_found", cert=str(cert_path))

    return cert_path, key_path


# ---------------------------------------------------------------------------
# Helper: resolve and validate the binding host
# ---------------------------------------------------------------------------

def _resolve_host(settings: dict[str, Any]) -> str:
    """Resolve the server binding host, enforcing the local-only security rule.

    Returns 127.0.0.1 unless security.api.allow_public_interface is explicitly
    true AND the configured host is 0.0.0.0.

    Args:
        settings: Parsed settings dictionary from settings.yaml.

    Returns:
        Resolved host string.
    """
    sec_cfg = get_security_config()
    allow_public = sec_cfg.get("security", {}).get("api", {}).get(
        "allow_public_interface", False
    )
    host = settings.get("api", {}).get("host", "127.0.0.1")

    if host == "0.0.0.0" and not allow_public:
        logger.warning(
            "host_restricted_to_localhost",
            requested=host,
            reason="security.api.allow_public_interface is false",
        )
        return "127.0.0.1"

    return host


# ---------------------------------------------------------------------------
# FastAPI application factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Create and configure the Renine Mobile API FastAPI application.

    Returns:
        Configured FastAPI instance.
    """

    @contextlib.asynccontextmanager  # type: ignore[arg-type]
    async def lifespan(application: FastAPI):  # type: ignore[misc]
        """Manage application startup and shutdown lifecycle."""
        # --- startup ---
        settings = get_settings()
        host = _resolve_host(settings)
        port = settings.get("api", {}).get("port", 8000)
        logger.info("api_server_starting", host=host, port=port)
        yield
        # --- shutdown ---
        logger.info("api_server_shutdown")

    app = FastAPI(
        title="Renine Mobile API",
        description="Local-network companion API for Project Renine.",
        version="8.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Attach rate limiter
    app.state.limiter = limiter

    # Custom exception handlers
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    @app.exception_handler(RenineError)
    async def renine_error_handler(request: Request, exc: RenineError) -> JSONResponse:
        """Map RenineError subclasses to structured JSON error responses."""
        logger.error("renine_error", path=str(request.url), error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": str(exc)},
        )

    # CORS: allow local-network origins only
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:*", "https://localhost:*",
                       "http://127.0.0.1:*", "https://127.0.0.1:*"],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # ----- Register routers -----
    from api.endpoints import router as endpoints_router
    app.include_router(endpoints_router)

    return app


# ---------------------------------------------------------------------------
# Application singleton (imported by uvicorn / tests)
# ---------------------------------------------------------------------------

app = create_app()


# ---------------------------------------------------------------------------
# Entry point: python -m api.server
# ---------------------------------------------------------------------------

def main() -> None:
    """Start the Uvicorn HTTPS server from command line.

    Reads host, port, and TLS paths from config/settings.yaml.
    Generates self-signed certificates if they are absent.
    Enforces local-only binding unless explicitly allowed.
    """
    import uvicorn

    settings = get_settings()
    host = _resolve_host(settings)
    raw_port = settings.get("api", {}).get("port", 8000)
    port = int(raw_port)

    cert_path, key_path = _ensure_ssl_certs(settings)

    logger.info("api_server_start", host=host, port=port)

    uvicorn.run(
        "api.server:app",
        host=host,
        port=port,
        ssl_keyfile=str(key_path),
        ssl_certfile=str(cert_path),
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
