# Phase 8 — Mobile Companion
## Phase Report

**Phase:** 8  
**Status:** In Progress — Milestone 1 COMPLETE  
**Started:** 2026-06-26  
**Last Updated:** 2026-06-26 (Milestone 1 complete)

---

## Objectives

Build a mobile-accessible interface for remote home management with:
- FastAPI server — local network only, HTTPS, JWT auth
- React Native (Expo) mobile app
- Authenticated API endpoints for memory, device control, pet status, reminders
- All responses through `ContextSanitizer`
- No direct database access from mobile — all queries mediated by API

---

## Milestone 1 — Server Infrastructure & Authentication ✅ COMPLETE

### Completed Work

| Item | File | Status |
|------|------|--------|
| Install dependencies | `pyproject.toml` | ✅ |
| API config | `config/settings.yaml` | ✅ |
| API security config | `config/security.yaml` | ✅ |
| API package init | `api/__init__.py` | ✅ |
| JWT auth utilities | `api/auth.py` | ✅ |
| Rate limiting | `api/rate_limiting.py` | ✅ |
| FastAPI server + HTTPS | `api/server.py` | ✅ |
| Login + health endpoints | `api/endpoints.py` | ✅ |
| Milestone 1 tests | `tests/api/test_server.py` | ✅ |

### Dependencies Added

- `fastapi>=0.110.0` (installed: 0.138.1)
- `pyjwt>=2.8.0` (installed: 2.13.0)
- `slowapi>=0.1.9` (installed: 0.1.10)
- `python-multipart>=0.0.9` (installed: 0.0.32)

### Files Created

| File | Purpose |
|------|---------|
| `api/__init__.py` | Package namespace |
| `api/auth.py` | JWT creation/verification, bcrypt password hashing, `get_current_user` FastAPI dependency |
| `api/rate_limiting.py` | SlowAPI limiter, configurable from `settings.yaml`, custom 429 handler |
| `api/server.py` | FastAPI app factory, self-signed TLS cert generation, local-only binding enforcement, lifespan event handler, CORS middleware |
| `api/endpoints.py` | `POST /api/auth/login`, `GET /api/health` |
| `tests/api/__init__.py` | Test package marker |
| `tests/api/test_server.py` | 31 Milestone 1 unit tests |

### Files Modified

| File | Change |
|------|--------|
| `pyproject.toml` | Added Phase 8 dependencies |
| `config/settings.yaml` | Added `api:` block with host/port/jwt/rate-limit config |
| `config/security.yaml` | Added `security.api` block with `allow_public_interface` flag and field whitelists |

### Architectural Decisions

1. **Lifespan over @on_event**: Used the modern `@contextlib.asynccontextmanager` lifespan pattern instead of deprecated `@app.on_event`. Eliminates DeprecationWarning on FastAPI 0.138.
2. **bcrypt for password hashing**: `bcrypt` was already installed in the environment. Used for password verification when `password_hash` config is set.
3. **Triple-priority password auth**: (1) `API_PASSWORD` env var (plain, for local dev), (2) `api.password_hash` config (bcrypt hash), (3) deny all if neither is set.
4. **Self-signed cert**: Uses `cryptography` library (already a dependency) to auto-generate a 2048-bit RSA cert with SAN for `renine.local` and `localhost`. Valid 365 days.
5. **Binding enforcement**: `_resolve_host()` checks `security.api.allow_public_interface`. If false (default), `0.0.0.0` is silently restricted to `127.0.0.1`.
6. **Module-level `app` singleton**: `api/server.py` creates `app = create_app()` at module level so Uvicorn can reference `api.server:app` directly. Tests that need the app use `create_app()`.

### Bugs Encountered & Fixed

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| `RuntimeError: Form data requires python-multipart` | FastAPI form login requires `python-multipart` not in initial deps | Installed and added to `pyproject.toml` |
| Deprecated `asyncio.get_event_loop()` in test | Python 3.13 deprecates this pattern outside an async context | Replaced with `asyncio.run()` |
| `on_event` deprecation warning | FastAPI 0.138 deprecated `@app.on_event` | Migrated to lifespan context manager |

### Test Count — Milestone 1

| Suite | Tests | Pass |
|-------|-------|------|
| `tests/api/test_server.py` | 31 | 31 ✅ |

---

## Milestone 2 — API Endpoints Integration 🔜 NEXT

### Planned Work

- Memory endpoints (Layer 1 context, Layer 2 history, Layer 3 Mind, Layer 4 Personality)
- ContextSanitizer integration and field whitelisting
- Smart Home endpoints (list, state, create/confirm actions)
- Pet endpoints (list, feed)
- Reminders endpoint (APScheduler job list)
- Milestone 2 tests

---

## Milestone 3 — Mobile App 📅 PENDING

---

## Milestone 4 — Final Regression & Documentation 📅 PENDING

---

## Performance Notes

- Server startup: < 1s (lazy DB connections)
- JWT decode: < 1ms per request
- Self-signed cert generation: ~300ms (one-time on first run)

---

## Known Issues

- `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2` — upstream library issue, not actionable yet.
- CORS `allow_origins` currently uses wildcard-style strings (`http://localhost:*`) which may not be supported by all browser implementations — will harden in Milestone 2 when actual mobile origins are known.
