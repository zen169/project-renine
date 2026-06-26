"""Renine Mobile API — route definitions.

Milestone 1 routes:
    POST /api/auth/login   — Exchange username + password for a JWT token.
    GET  /api/health       — Unauthenticated health check (server liveness probe).

Milestone 2 routes (Memory, Smart Home, Pets, Reminders) are now fully implemented.
"""
from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from renine.core.config import get_settings
from renine.core.logging_config import get_logger
from api.auth import create_access_token, get_current_user, verify_password
from api.rate_limiting import limiter
from api.models import (
    TokenResponse,
    HealthResponse,
    ContextResponse,
    HistoryResponse,
    MindResponse,
    PersonalityResponse,
    DeviceListResponse,
    DeviceStateResponse,
    CreateActionRequest,
    CreateActionResponse,
    ConfirmActionResponse,
    PetListResponse,
    FeedResponse,
    RemindersResponse,
)
from api.dependencies import (
    get_layer1_context,
    get_layer2_history,
    get_layer3_mind,
    get_layer4_personality,
    get_smart_devices,
    get_smart_device_by_entity,
    create_pending_action,
    confirm_pending_action,
    get_pets,
    feed_pet,
    get_scheduled_reminders,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api")


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


# ---------------------------------------------------------------------------
# GET /api/memory/context
# ---------------------------------------------------------------------------

@router.get(
    "/memory/context",
    response_model=ContextResponse,
    summary="Get conversation context",
)
@limiter.limit("60/minute")
async def get_context(
    request: Request,
    current_user: Annotated[str, Depends(get_current_user)],
) -> ContextResponse:
    """Retrieve the current active conversation context (Layer 1)."""
    messages = get_layer1_context()
    return ContextResponse(messages=messages, count=len(messages))


# ---------------------------------------------------------------------------
# GET /api/memory/history
# ---------------------------------------------------------------------------

@router.get(
    "/memory/history",
    response_model=HistoryResponse,
    summary="Get conversation history",
)
@limiter.limit("60/minute")
async def get_history(
    request: Request,
    current_user: Annotated[str, Depends(get_current_user)],
    limit: int = 20,
) -> HistoryResponse:
    """Retrieve recent conversation summary history (Layer 2)."""
    conversations = get_layer2_history(limit=limit)
    return HistoryResponse(conversations=conversations, count=len(conversations))


# ---------------------------------------------------------------------------
# GET /api/memory/mind
# ---------------------------------------------------------------------------

@router.get(
    "/memory/mind",
    response_model=MindResponse,
    summary="Get facts from mind database",
)
@limiter.limit("60/minute")
async def get_mind(
    request: Request,
    current_user: Annotated[str, Depends(get_current_user)],
    namespace: str,
    query: str | None = None,
    limit: int = 50,
) -> MindResponse:
    """Retrieve facts from the mind database (Layer 3), filtered by whitelist."""
    records = get_layer3_mind(namespace=namespace, query=query, limit=limit)
    return MindResponse(records=records, count=len(records), namespace=namespace)


# ---------------------------------------------------------------------------
# GET /api/memory/personality
# ---------------------------------------------------------------------------

@router.get(
    "/memory/personality",
    response_model=PersonalityResponse,
    summary="Get profiles from personality database",
)
@limiter.limit("60/minute")
async def get_personality(
    request: Request,
    current_user: Annotated[str, Depends(get_current_user)],
    query: str | None = None,
    limit: int = 50,
) -> PersonalityResponse:
    """Retrieve people profiles (Layer 4), filtered by whitelist."""
    people = get_layer4_personality(query=query, limit=limit)
    return PersonalityResponse(people=people, count=len(people))


# ---------------------------------------------------------------------------
# GET /api/smart-home/devices
# ---------------------------------------------------------------------------

@router.get(
    "/smart-home/devices",
    response_model=DeviceListResponse,
    summary="List cached smart devices",
)
@limiter.limit("60/minute")
async def list_devices(
    request: Request,
    current_user: Annotated[str, Depends(get_current_user)],
    domain: str | None = None,
) -> DeviceListResponse:
    """Retrieve cached smart home devices from the local database."""
    devices = get_smart_devices(domain=domain)
    return DeviceListResponse(devices=devices, count=len(devices))


# ---------------------------------------------------------------------------
# GET /api/smart-home/devices/{entity_id}
# ---------------------------------------------------------------------------

@router.get(
    "/smart-home/devices/{entity_id}",
    response_model=DeviceStateResponse,
    summary="Get specific smart device state",
)
@limiter.limit("60/minute")
async def get_device_state(
    request: Request,
    entity_id: str,
    current_user: Annotated[str, Depends(get_current_user)],
) -> DeviceStateResponse:
    """Retrieve the cached state and attributes of a specific device."""
    device = get_smart_device_by_entity(entity_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Smart device with entity ID '{entity_id}' not found.",
        )
    return DeviceStateResponse(**device)


# ---------------------------------------------------------------------------
# POST /api/smart-home/actions
# ---------------------------------------------------------------------------

@router.post(
    "/smart-home/actions",
    response_model=CreateActionResponse,
    summary="Create a pending smart home action",
)
@limiter.limit("60/minute")
async def create_action(
    request: Request,
    action_req: CreateActionRequest,
    current_user: Annotated[str, Depends(get_current_user)],
) -> CreateActionResponse:
    """Create a new pending smart home action requiring confirmation."""
    entity_id = action_req.entity_id
    service = action_req.service
    if "." not in entity_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid entity_id format. Must be 'domain.name'.",
        )
    domain = entity_id.split(".", 1)[0]
    try:
        action = create_pending_action(entity_id=entity_id, domain=domain, service=service)
        return CreateActionResponse(
            action=action,
            message="Smart home action created. Confirmation required.",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# POST /api/smart-home/actions/{action_id}/confirm
# ---------------------------------------------------------------------------

@router.post(
    "/smart-home/actions/{action_id}/confirm",
    response_model=ConfirmActionResponse,
    summary="Confirm and execute a pending action",
)
@limiter.limit("60/minute")
async def confirm_action(
    request: Request,
    action_id: int,
    current_user: Annotated[str, Depends(get_current_user)],
) -> ConfirmActionResponse:
    """Execute a pending smart home action by ID after confirmation."""
    try:
        result = confirm_pending_action(action_id)
        return ConfirmActionResponse(**result)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# GET /api/pets
# ---------------------------------------------------------------------------

@router.get(
    "/pets",
    response_model=PetListResponse,
    summary="List household pets",
)
@limiter.limit("60/minute")
async def list_pets(
    request: Request,
    current_user: Annotated[str, Depends(get_current_user)],
) -> PetListResponse:
    """Retrieve household pets, excluding sensitive medical details."""
    pets = get_pets()
    return PetListResponse(pets=pets, count=len(pets))


# ---------------------------------------------------------------------------
# POST /api/pets/{name}/feed
# ---------------------------------------------------------------------------

@router.post(
    "/pets/{name}/feed",
    response_model=FeedResponse,
    summary="Record a pet feeding event",
)
@limiter.limit("60/minute")
async def feed_pet_endpoint(
    request: Request,
    name: str,
    current_user: Annotated[str, Depends(get_current_user)],
) -> FeedResponse:
    """Record a feeding event for the named pet."""
    try:
        success = feed_pet(name)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Pet named '{name}' not found.",
            )
        return FeedResponse(
            success=True,
            message=f"{name} has been successfully marked as fed.",
            pet_name=name,
        )
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# GET /api/reminders
# ---------------------------------------------------------------------------

@router.get(
    "/reminders",
    response_model=RemindersResponse,
    summary="Get scheduled reminders",
)
@limiter.limit("60/minute")
async def list_reminders(
    request: Request,
    current_user: Annotated[str, Depends(get_current_user)],
) -> RemindersResponse:
    """Retrieve active scheduled reminders from the system scheduler."""
    reminders = get_scheduled_reminders()
    return RemindersResponse(reminders=reminders, count=len(reminders))
