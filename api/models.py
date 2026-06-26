"""Pydantic response/request schemas for the Renine Mobile API.

Milestone 2 schemas cover:
    - Memory (Layer 1 context, Layer 2 history, Layer 3 mind, Layer 4 personality)
    - Smart Home (devices, pending actions)
    - Pets
    - Reminders (APScheduler jobs)

All schemas are strict in what they return — only the fields listed
in security.yaml security.api.whitelisted_fields are allowed through for
Layer 3 and Layer 4 responses.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Auth / Health (Milestone 1 — kept here for centralisation)
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
# Memory — Layer 1 (Conversation Context)
# ---------------------------------------------------------------------------

class ContextMessageSchema(BaseModel):
    """Single turn in the active conversation context."""
    role: str
    content: str


class ContextResponse(BaseModel):
    """Layer 1 conversation context response."""
    messages: list[ContextMessageSchema]
    count: int


# ---------------------------------------------------------------------------
# Memory — Layer 2 (Conversation History)
# ---------------------------------------------------------------------------

class ConversationSummarySchema(BaseModel):
    """A past conversation entry from Layer 2."""
    id: int
    date: str | None
    summary: str
    created_at: str


class HistoryResponse(BaseModel):
    """Layer 2 conversation history response."""
    conversations: list[ConversationSummarySchema]
    count: int


# ---------------------------------------------------------------------------
# Memory — Layer 3 (Mind / Facts) — whitelisted fields only
# ---------------------------------------------------------------------------

class MindRecordSchema(BaseModel):
    """A single fact from the Mind database (whitelisted fields only).

    The 'value' JSON field is intentionally excluded — it may contain
    sensitive personal data. Only the summary and metadata are returned.
    """
    id: int
    namespace: str
    key: str
    summary: str
    created_at: str
    updated_at: str


class MindResponse(BaseModel):
    """Layer 3 mind database response."""
    records: list[MindRecordSchema]
    count: int
    namespace: str | None = None


# ---------------------------------------------------------------------------
# Memory — Layer 4 (Personality / People) — whitelisted fields only
# ---------------------------------------------------------------------------

class PersonSchema(BaseModel):
    """A person profile (whitelisted fields only).

    Deep personal data (notes, food_preferences, hobbies, personality_traits,
    goals, habits) is intentionally excluded from API responses.
    """
    name: str
    relationship: str
    age: int | None
    birthday: str | None
    updated_at: str


class PersonalityResponse(BaseModel):
    """Layer 4 personality database response."""
    people: list[PersonSchema]
    count: int


# ---------------------------------------------------------------------------
# Smart Home — Device list and state
# ---------------------------------------------------------------------------

class SmartDeviceSchema(BaseModel):
    """A cached smart home device entity."""
    id: int
    entity_id: str
    name: str
    domain: str
    state: str
    last_synced: str | None
    updated_at: str


class DeviceListResponse(BaseModel):
    """Response for GET /api/smart-home/devices."""
    devices: list[SmartDeviceSchema]
    count: int


class DeviceStateResponse(BaseModel):
    """Response for GET /api/smart-home/devices/{entity_id}."""
    entity_id: str
    name: str
    domain: str
    state: str
    attributes: dict[str, Any]
    last_synced: str | None


# ---------------------------------------------------------------------------
# Smart Home — Pending Actions
# ---------------------------------------------------------------------------

class CreateActionRequest(BaseModel):
    """Request body for POST /api/smart-home/actions."""
    entity_id: str
    service: str


class PendingActionSchema(BaseModel):
    """A pending smart home confirmation action."""
    id: int
    entity_id: str
    domain: str
    service: str
    status: str
    requested_at: str
    expires_at: str


class CreateActionResponse(BaseModel):
    """Response for POST /api/smart-home/actions."""
    action: PendingActionSchema
    message: str


class ConfirmActionResponse(BaseModel):
    """Response for POST /api/smart-home/actions/{action_id}/confirm."""
    success: bool
    message: str
    entity_id: str | None = None
    service: str | None = None


# ---------------------------------------------------------------------------
# Pets
# ---------------------------------------------------------------------------

class FeedingScheduleEntrySchema(BaseModel):
    """A single feeding schedule entry."""
    time: str | None = None
    amount: str | None = None


class PetSchema(BaseModel):
    """A household pet (safe fields only — no medical conditions detail)."""
    id: int
    name: str
    species: str
    breed: str | None
    age: float | None
    feeding_schedule: list[dict[str, Any]]
    last_fed: str | None
    updated_at: str


class PetListResponse(BaseModel):
    """Response for GET /api/pets."""
    pets: list[PetSchema]
    count: int


class FeedResponse(BaseModel):
    """Response for POST /api/pets/{name}/feed."""
    success: bool
    message: str
    pet_name: str


# ---------------------------------------------------------------------------
# Reminders (APScheduler jobs)
# ---------------------------------------------------------------------------

class ReminderSchema(BaseModel):
    """A single scheduled reminder (APScheduler job)."""
    id: str
    name: str | None
    next_run_time: str | None


class RemindersResponse(BaseModel):
    """Response for GET /api/reminders."""
    reminders: list[ReminderSchema]
    count: int
