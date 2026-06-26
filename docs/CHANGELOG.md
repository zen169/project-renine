# PROJECT RENINE - Changelog
All notable changes listed newest-first.

---

## [0.7.0] - Phase 7B (2026-06-26)
### Phase 7B - Safe Smart Home Device Control [COMPLETE]
- Implemented database-backed confirmation actions (PendingSmartHomeAction) using mind.db (MindBase).
- Implemented Alembic migration for the `pending_smart_home_actions` table.
- Implemented `HassClient.call_service()` supporting POST requests for allowlisted service calls.
- Implemented SmartHomeAgent confirmation gate flow (`yes`/`confirm`/`y` logic with 5-minute TTL).
- Enforced strict allowlist validation for domains (`light`, `switch`, `fan`, `cover`) and services (`turn_on`, `turn_off`, `toggle`, `open_cover`, `close_cover`, `stop_cover`) before initiating any API calls.
- Resolved timezone offset comparison issue by standardizing on timezone-aware UTC datetime operations inside the ORM model's `is_expired()` method.
- Added comprehensive unit tests for `call_service()` allowlisting and confirmation gate flow validation.

**Files modified/created:**
- renine/databases/models/pending_smart_home_action.py [NEW]
- renine/databases/models/__init__.py [MODIFIED]
- renine/databases/migrations/versions/a1b2c3d4e5f6_add_pending_smart_home_actions_table.py [NEW]
- renine/tools/smart_home/hass_client.py [MODIFIED]
- renine/agents/smart_home_agent.py [MODIFIED]
- config/tools.yaml [MODIFIED]
- tests/tools/test_hass_client.py [MODIFIED]
- tests/agents/test_smart_home_agent.py [MODIFIED]

---

## [0.7.0-alpha] - Phase 7A (2026-06-26)
### Phase 7A - Read-Only Smart Home Integration
- Implemented HassClient with persistent httpx.Client (GET-only)
- Implemented SmartHomeAgent (read-only): sync_devices, get_device_status, list_cached_devices, check_connection
- Created SmartDevice ORM model and Alembic migration (smart_devices table)
- Integrated SmartHomeAgent routing in router.py
- Integrated SmartHomeAgent dispatch in ipc_handlers.ts
- Added comprehensive Phase 7A unit tests
- Fixed: SmartDevice._upsert_device uses explicit SELECT pattern (no merge())
- Fixed: All timestamps are timezone-aware (datetime.now(UTC))

**Files modified:** hass_client.py (new), smart_home_agent.py (new), smart_device.py (new), models/__init__.py, agents/__init__.py, router.py, ipc_handlers.ts, test_smart_home_agent.py (new), test_router.py, test_ipc_phase6_dispatch.py, tools.yaml

---

## [0.6.0] - Phase 6 (2026-06-25)
### Phase 6 - Web Operations
- Implemented BrowserAgent, EmailAgent, NewsAgent, external LLM client
- Playwright browser tool with isolated profiles and verified cleanup
- Hardened Gmail OAuth: readonly default, compose opt-in, send blocked
- Browser content marked UNTRUSTED; Layer 3/4 memory access denied
- Integrated BrowserAgent, EmailAgent, NewsAgent into Electron IPC dispatch
- Tests: 256/256 passing

---

## [0.5.0] - Phase 5 (2026-06-18)
### Phase 5 - Vision Integration
- Screenshot capture (mss), OCR/VQA (Qwen2.5-VL via Ollama), Webcam (OpenCV)
- VisionAgent orchestrating all vision requests
- Tests: 224/224 passing

---

## [0.4.0] - Phase 4 (2026-06-18)
### Phase 4 - Desktop Control & File Management
- AppLauncher, VolumeControl, Clipboard tools
- FileReader, PDFReader, FileSearch, file_index cache
- FileAgent, CodingAgent, SpreadsheetAgent
- Tests: 188/188 passing

---

## [0.3.0] - Phase 3 (2026-06-18)
### Phase 3 - Personal Databases
- InventoryAgent, PetAgent, HouseAgent
- Alembic migrations for mind.db tables
- APScheduler-based pet feeding reminders
- Tests: 168/168 passing

---

## [0.2.0] - Phase 2 (2026-06-18)
### Phase 2 - Memory System
- 4-layer memory: SQLite + ChromaDB
- BGE-M3 embeddings, MemoryAgent
- Tests: 157/157 passing

---

## [0.1.0] - Phase 1 (2026-06-18)
### Phase 1 - MVP Foundation
- Core modules, router, MainBrainAgent, voice pipeline, security
- Tests: 133/133 passing
