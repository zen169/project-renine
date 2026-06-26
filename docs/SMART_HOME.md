# PROJECT RENINE - Smart Home Integration
Last Updated: 2026-06-26

---

## Overview

Renine integrates with Home Assistant (HASS) via its REST API.

## Architecture

### HassClient (renine/tools/smart_home/hass_client.py)
- Persistent httpx.Client: base_url, Bearer auth, Timeout(10.0), follow_redirects
- Context manager: with HassClient() as client
- Token from env var HASS_TOKEN

### SmartHomeAgent (renine/agents/smart_home_agent.py)
- Inherits BaseAgent; NO httpx import
- Phase 7A: READ_ONLY permission
- Phase 7B: STANDARD permission (device control with confirmation)

### Database Tables (mind.db / MindBase)
- smart_devices: entity_id(UNIQUE), name, domain, state, attributes(JSON), timestamps
- pending_smart_home_actions [Phase 7B]: id, entity_id, domain, service, service_data, requested_at, expires_at, status

## Phase 7A Capabilities (COMPLETE)

| Op | HTTP | Endpoint |
|--|--|--|
| sync_devices | GET | /api/states |
| get_entity_state | GET | /api/states/{entity_id} |
| check_connection | GET | /api/ |

Agent commands: sync, discover, refresh, status {id}, list devices, connection, ping

## Phase 7B Capabilities (COMPLETE)

Allowed domains: light, switch, fan, cover
Allowed services: turn_on, turn_off, toggle, open_cover, close_cover, stop_cover
NOT allowed: lock, thermostat, climate, alarm, any unlisted domain

### Confirmation Gate Flow
1. User: Turn off the living room lights
2. Agent detects control intent, resolves entity_id + service
3. Agent stores PendingSmartHomeAction in DB (TTL 5 min)
4. Agent returns prompt asking for confirmation
5. User: yes / confirm / y
6. Agent finds pending action, checks not expired, calls HassClient.call_service()
7. HassClient POSTs /api/services/{domain}/{service}
8. Result returned; DB record marked executed

## Exception Hierarchy

HassError > HassConnectionError, HassAuthError, HassResponseError, HassServiceError

## Known Limitations

1. Cache updated on explicit sync only (no WebSocket push)
2. Confirmation must occur in same session
3. No thermostat/climate in Phase 7B

## Future Roadmap

- Phase 8+: WebSocket real-time state push
- Phase 8+: Automations and scene triggering
- Long term: Thermostat with safety bounds
