
<!--
Copyright (c) 2025 harokku999@gmail.com
Licensed under the MIT License - https://opensource.org/licenses/MIT
-->

## 🔗 REST/JSON APIs for Nextcloud

This service wraps Nextcloud CardDAV and CalDAV endpoints with modern REST/JSON APIs so that automations, dashboards, and other services can manage contacts and calendar events without wrestling with WebDAV. It ships with both local Python tooling and a Docker workflow so you can choose the runtime that best fits your environment.

## Features

- CRUD APIs for contacts and events backed by Nextcloud
- Native CardDAV/CalDAV integration with optional field masking
- HTTP Basic auth enforced at the API layer
- OpenAPI/Swagger UI served directly by FastAPI
- Comprehensive pytest suite covering API and CLI entry points

---

## Prerequisites

- Python 3.12+
- Docker / Docker Compose (optional but recommended for deployment)
- Access to a Nextcloud instance with CardDAV/CalDAV enabled

## Configuration

Copy and edit the example configuration files so the API knows how to reach your Nextcloud instance:

- `app/src/api/config.example.yaml` → `app/src/api/config.yaml`
- `app/src/nextcloud/config.example.yaml` → `app/src/nextcloud/config.yaml`

Populate metadata (service name, bind host/port) plus the credentials or tokens needed to connect to Nextcloud. Docker users should also create a `.env` file in the repo root and set `FASTAPI_PORT=<port>` to control how the container exposes the service.

---

## Running the API

### Option A — Local Python
```bash
git clone https://gitlab.com/your-username/your-repo.git
cd your-repo
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt

# After configuring the YAML files mentioned above:
python -m app.fastapi4nx
```

The server defaults to `http://localhost:1265` (override in config). Useful endpoints:

- Docs/UI: `http://localhost:<port>/docs`
- Contacts API: `http://localhost:<port>/contacts`
- Events API: `http://localhost:<port>/events`
- Status probe: `http://localhost:<port>/status`

### Option B — Docker / Docker Compose

#### Compose (recommended)
```bash
FASTAPI_PORT=1265 docker compose up --build
```
`docker-compose.yaml` builds the image, loads environment variables from `.env`, and maps `<FASTAPI_PORT>` automatically.

#### Manual docker build/run
```bash
docker build -t fastapi4nx .
docker run --rm -p 1265:1265 --env-file .env fastapi4nx
```

The provided `Dockerfile` sets `PYTHONPATH=/app/app` and runs `python -m app.fastapi4nx` so the same configuration files are honored inside the container.

---

## API Highlights

### Events API

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/events/{uid}` | Fetch one event; supports optional masking for private data |
| `GET` | `/events` | List events in a time range, sorted chronologically |
| `POST` | `/events` | Create a new event (UID auto-generated if not supplied) |
| `PUT` | `/events/{uid}` | Update an existing event |
| `DELETE` | `/events/{uid}` | Delete an event permanently |

Common query parameters:
- `calendar_name` – target a specific Nextcloud calendar (defaults to `personal`).
- `privacy` – when `true`, masks sensitive fields on read operations.

Example:
```bash
curl -u alice:secret \
  "http://localhost:1265/events?start_datetime=2025-04-21T00:00:00&end_datetime=2025-04-28T23:59:59&privacy=true"
```

The contacts API follows the same REST conventions for managing CardDAV-backed contact records.

### Authentication

All endpoints require HTTP Basic Authentication using your Nextcloud credentials. Requests without valid auth receive `401 Unauthorized`.

---

## Testing

Run the full suite (covers CLI helpers and API flows):
```bash
pytest app/tests -v
```

Individual modules can be invoked similarly, e.g. `python -m app.tests.test_contacts_api_cli`.

---

## Roadmap

- **Recurring event support**: expose structured recurrence editing (RRULE/EXDATE/RDATE) and instance overrides so clients can create and manage repeating meetings directly through the REST API.

---

## Contributing

Bug reports, docs fixes, and feature ideas are welcome—open an issue or reach out if you’d like to collaborate.

## License

Released under the [MIT License](https://choosealicense.com/licenses/mit/) © harokku999@gmail.com (2025).

---

## Changelogs

### 2026-01-30 — Async Auth & Optimistic Locking
- Replaced the blocking `requests`-based Nextcloud auth check with an async `httpx` client, plus retry/backoff and a circuit breaker to keep the API responsive when OCS hiccups.
- Added pooled aiohttp sessions with configurable timeouts/proxy support so CardDAV/CalDAV calls reuse connections instead of rebuilding TLS handshakes per request.
- Surfaced ETag metadata through the models and send `If-Match` headers on writes to prevent silent contact/event overwrites; every mutation now records a JSONL audit entry for rollback debugging.
- Conflict responses now return `412` along with the latest payload/ETag so clients can refresh without an extra read, and pytest optimistically simulates concurrent updates to assert both the HTTP behavior and the audit-log trail.

### 2025-12-01 — DAV Client Refactor
- Introduced shared `CardDavClient`/`CalDavClient` helpers so the API modules no longer duplicate aiohttp plumbing.
- Centralized header creation, XML payload generation, and response handling inside the new clients to simplify `contacts.py` and `events.py`.
- Kept the existing parsing/masking helpers untouched, ensuring business logic remains consistent while the transport layer is cleaner.

### 2025-11-25 — Reminder & Test Refactor
- Added timezone-aware reminder handling so absolute alarms preserve TZIDs end-to-end.
- Introduced shared reminder/timezone utility modules to keep CalDAV parsing/writing consistent.
- Refactored CLI-style tests to use reusable API clients and helper modules, reducing boilerplate and improving maintainability.
- Moved test-only configuration into dedicated support modules to decouple it from production settings.
