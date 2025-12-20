
<!--
Copyright (c) 2025 harokku999@gmail.com
Licensed under the MIT License - https://opensource.org/licenses/MIT
-->

## 🔗 REST/JSON APIs for Nextcloud

This project exposes Nextcloud’s CalDAV and CardDAV interfaces as modern, developer-friendly REST/JSON APIs. Use simple HTTP requests and JSON payloads to read, create, update, or delete calendar events and contact records without dealing with legacy WebDAV protocols directly.

## Features

- REST API for contacts, events, and tasks (VTODO)
- Recurring helpers: expand instances, build/preview RRULEs, add exceptions, and skip occurrences (events + tasks)
- Comprehensive CardDAV/CalDAV integration with short-lived per-user caches and cache headers
- Secure HTTP Basic auth with single-pass Nextcloud auth reuse per request
- Rich test coverage (API + direct CalDAV/CardDAV) and Swagger UI documentation

## Roadmap

- Version 0.3.3 : Refactoring to be fully docker-ized (in progress)

## Installation

1. Clone the repository:
```bash
git clone https://gitlab.com/your-username/your-repo.git
cd your-repo
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Linux/MacOS
# or
.\venv\Scripts\activate  # Windows
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and update values (FastAPI host/port, Nextcloud URLs, cache settings, and credentials). Environment variables are loaded and validated at runtime via `src/settings.py`; YAML config files are no longer used.

## Usage

Run directly using the script:
```bash
python fastapi4nx.py
```

The server will be available at `http://localhost:<your port>` with the following endpoints:
- API Documentation: `http://localhost:<your port>/docs`
- Contacts API: `http://localhost:<your port>/contacts`
- Events API: `http://localhost:<your port>/events`
- Tasks API: `http://localhost:<your port>/tasks`
- Status: `http://localhost:<your port>/status`

## API Documentation

The API provides comprehensive endpoints for managing contacts, events, and tasks in Nextcloud.

### Events (high level)
- CRUD: `/events`, `/events/{uid}`
- Recurring helpers: `/events/recurring/{uid}/instances`, `/events/recurring/rule`, `/events/recurring/preview`, `/events/recurring/{uid}/exception`, `/events/recurring/{uid}/skip`
- Calendars: `/events/calendars`

### Tasks (high level)
- CRUD: `/tasks`, `/tasks/{uid}`
- Recurring helpers: `/tasks/recurring/{uid}/instances`, `/tasks/recurring/rule`, `/tasks/recurring/preview`, `/tasks/recurring/{uid}/exception`, `/tasks/recurring/{uid}/skip`
- Calendars: `/tasks/calendars`

### Contacts (high level)
- CRUD + search: `/contacts`, `/contacts/{uid}`
- Address books: `/contacts/addressbooks`

### Authentication

All API endpoints require HTTP Basic Authentication with your Nextcloud credentials.

## Testing
Run all tests:
```bash
pytest tests/ -v
```

Or run individual test modules:

```bash
# Test contacts directly with Nextcloud (no FastAPI server needed)
python -m tests.test_contacts_nx_cli

# Test events directly with Nextcloud (no FastAPI server needed)
python -m tests.test_events_nx_cli

# Test contacts via the FastAPI server (requires server to be running)
python -m tests.test_contacts_api_cli

# Test events via the FastAPI server (requires server to be running)
python -m tests.test_events_api_cli

# Test recurring events helpers via the FastAPI server
python -m tests.test_recurring_events_api_cli

# Test tasks (including recurring helpers) via the FastAPI server
python -m tests.test_tasks_api_cli
python -m tests.test_recurring_tasks_api_cli
```

## Contributing
Let me know if you want to participate and how!

## License
**License**: [MIT](https://choosealicense.com/licenses/mit/)
**Author**: harokku999@gmail.com

## Changelog

### 0.3.2
- Fixed logging context to populate the user on cached auth and preserve explicit `extra` fields.
- Added recurring helpers for events and tasks (preview/rule build, instance expansion, exceptions, skips).
- Added tasks (VTODO) parity with events, including recurring flows and API routes.
- Added CLI API tests for recurring events/tasks.
- Switched configuration to environment variables; added `.env.example` and removed YAML configs.
- Made Nextcloud authentication async with hashed cache keys and single-pass auth per request.
- Added runtime config loader in `create_app` and removed module-level config globals.
- Renamed env vars to `NEXTCLOUD_INTERNET_URL` and `NEXTCLOUD_INTRANET_URL`.
- Updated tests to use env-driven proxy URL and user fixtures via `COMMON_USERS_YAML`.
- Added short-lived in-memory caches for read endpoints (events/contacts) with cache headers for agents, plus write-through invalidation and per-request auth/session reuse for CalDAV/CardDAV.
