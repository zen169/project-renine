# PROJECT RENINE — Architecture Reference
Last Updated: 2026-06-26
Version: 0.7.0 (Phase 7B Complete)

---

## System Overview

Renine is a local-first AI butler running on Windows 11.
All intelligence lives in the Python backend. The Electron frontend is a thin UI shell.

Pipeline: Human → Wake Word → STT → Router → Agent → Brain/DB/Tools → TTS → Human

---

## High-Level Module Map

### renine/core/
- config.py: YAML config loader (get_settings(), get_project_root())
- logging_config.py: structlog with daily file rotation
- exceptions.py: Full exception hierarchy rooted at RenineError
- events.py: Synchronous pub/sub event bus
- context_sanitizer.py: Strips sensitive data before external API calls

### renine/brain/
- router.py: Keyword-based input router → RouteDecision(target, confidence)
- ollama_client.py: Sync + async streaming to Qwen3:8B via Ollama
- external_client.py: External LLM fallback with ContextSanitizer enforcement
- response_builder.py: Assembles structured RenineResponse objects

### renine/agents/ (all inherit BaseAgent)
| Agent               | Phase | Domain                                      |
|---------------------|-------|---------------------------------------------|
| MainBrainAgent      | 1     | General conversation via Ollama             |
| MemoryAgent         | 2     | Memory retrieval from Layers 2-4            |
| InventoryAgent      | 3     | Food/supply inventory (mind.db)             |
| PetAgent            | 3     | Pet records + feeding reminders (mind.db)   |
| HouseAgent          | 3     | Room/appliance tracking (mind.db)           |
| FileAgent           | 4     | File search + file_index cache              |
| CodingAgent         | 4     | Code explanation/generation via Ollama      |
| SpreadsheetAgent    | 4     | CSV/Excel data analytics via pandas         |
| VisionAgent         | 5     | Screenshot, OCR, webcam capture             |
| BrowserAgent        | 6     | Web search via Playwright (UNTRUSTED)       |
| EmailAgent          | 6     | Gmail read (readonly scope, blocked send)   |
| NewsAgent           | 6     | RSS feed headlines + local summarization    |
| SmartHomeAgent      | 7     | HA entity cache + control (Phase 7B)        |

### renine/memory/ — Four-Layer Memory Architecture
- Layer 1: In-memory rolling context window (max 50 msgs, session-scoped)
- Layer 2: SQLite history.db — 48h TTL conversation history
- Layer 3: SQLite + ChromaDB mind.db — facts, devices, inventory, pets, house
- Layer 4: SQLite + ChromaDB personality.db — people profiles

### renine/databases/
- session.py: get_session(db_key) → SQLAlchemy Session
- models/: ORM models for all three databases
- migrations/: Alembic multi-database migrations (versions/ directory)

### renine/tools/
- permissions.py: PermissionLevel enum (single source of truth)
- registry.py: @register_tool decorator + ToolRegistry
- executor.py: Safe execution with permission checks
- smart_home/hass_client.py: HA REST client (Phase 7)

### renine/security/
- input_validator.py: Text, path, shell input validation
- confirmation_gate.py: Destructive action gating
- encryption.py: Fernet symmetric encryption

### renine/ui/ (Electron)
- electron/main.ts: Window creation, security hardening
- electron/preload.ts: contextBridge with channel whitelisting
- electron/ipc_handlers.ts: IPC routing → Python subprocess via stdin
- renderer/: HTML/React UI components

---

## Database Schema

### history.db (Layer 2 — HistoryBase)
- conversations: id, session_id, role, content, timestamp

### mind.db (Layer 3 — MindBase)
- mind_records: namespace, key, value, embedding_id, created_at
- inventory_items: id, name, category, quantity, unit, threshold, location, expiration_date
- pets: id, name, species, breed, age, weight, feeding_schedule, medical_conditions, medications, last_fed
- house_items: id, room, item_type, name, description, location
- file_index: id, path, filename, extension, size, last_modified, content_preview
- smart_devices: id, entity_id (UNIQUE), name, domain, state, attributes (JSON), last_changed, last_updated, last_synced, created_at, updated_at
- pending_smart_home_actions: [Phase 7B NEW] id, entity_id, domain, service, service_data (JSON), requested_at, expires_at, status

### personality.db (Layer 4 — PersonalityBase)
- people: id, name, relationship, age, birthday, food_preferences, hobbies, personality_traits, goals, habits, notes

---

## Routing Logic (router.py)

Router is purely keyword-based. First match wins:
1. Inventory keywords → InventoryAgent
2. House keywords → HouseAgent
3. Pet keywords → PetAgent
4. Vision keywords → VisionAgent
5. Email keywords → EmailAgent
6. News keywords → NewsAgent
7. Browser keywords → BrowserAgent
8. Smart home keywords → SmartHomeAgent  [Phase 7]
9. Default → MainBrainAgent

Phase 7B adds: turn on/off/toggle/open/close/stop → SmartHomeAgent

---

## IPC Dispatch (ipc_handlers.ts)

Electron IPC runs Python via stdin subprocess. On renine:send-message:
1. route(user_input) → RouteDecision
2. Instantiate matching agent based on target
3. agent.process(user_input) → JSON → renderer

---

## HassClient Architecture

- Location: renine/tools/smart_home/hass_client.py
- Uses persistent httpx.Client (base_url, auth headers, 10s timeout, follow_redirects)
- Context manager: with HassClient() as client:
- Phase 7A: GET-only (discover_entities, get_entity_state, check_connection)
- Phase 7B: adds _call_service(domain, service, entity_id, service_data) via POST
  - Allowlisted domains: light, switch, fan, cover
  - Allowlisted services: turn_on, turn_off, toggle, open_cover, close_cover, stop_cover

---

## Security Constraints

- No HTTP in agents (only HassClient may make HTTP requests)
- HassClient GET-only in Phase 7A; POST only for allowlisted services in Phase 7B
- Confirmation gate mandatory for all state-changing actions
- Pending actions expire after 5 minutes (TTL enforced by DB model)
- smart_home_enabled feature flag checked at process() entry
- Browser content marked UNTRUSTED; Layer 3/4 memory denied
- Gmail send blocked; default scope is readonly
- Path traversal prevention in input_validator.py

---

## Key Design Principles

1. Local-first — No cloud dependency; all AI inference is local via Ollama
2. HassClient is the sole HTTP component — No agent imports httpx directly
3. Database writes are local cache only — HASS is the source of truth
4. Explicit over implicit — No Session.merge(); select → update/insert pattern
5. Timezone-aware timestamps — datetime.now(UTC), never utcnow()
6. Confirmation gate for all device control — No action without explicit user confirmation
7. Allowlist-only services — Only explicitly enumerated HASS service calls permitted
