
<!--
Copyright (c) 2025 harokku999@gmail.com
Licensed under the MIT License - https://opensource.org/licenses/MIT
-->

## 🔗 REST/JSON APIs for Nextcloud

This project exposes Nextcloud’s CalDAV and CardDAV interfaces as modern, developer-friendly REST/JSON APIs. Use simple HTTP requests and JSON payloads to read, create, update, or delete calendar events and contact records without dealing with legacy WebDAV protocols directly.

## Features

- REST API for contacts and events management
- Comprehensive CardDAV/CalDAV integration with Nextcloud
- Secure authentication handling
- Comprehensive test coverage
- Swagger UI documentation

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

The application requires configuration to connect to your Nextcloud instance. Copy the example YAML files and adjust them for your environment:

- `src/api/config.example.yaml` → `src/api/config.yaml`
- `src/nextcloud/config.example.yaml` → `src/nextcloud/config.yaml`

Update these files with the details for your deployment (service metadata, host/port, and Nextcloud connection settings) before starting the API server.

## Usage

Run directly using the script:
```bash
python fastapi4nx.py
```

The server will be available at `http://localhost:<your port>` with the following endpoints:
- API Documentation: `http://localhost:<your port>/docs`
- Contacts API: `http://localhost:<your port>/contacts`
- Events API: `http://localhost:<your port>/events`
- Status: `http://localhost:<your port>/status`

## Docker

A root-level [README](../README.md) explains how to build the container image and run the service with Docker or docker-compose. Follow those instructions if you prefer an isolated environment over the local Python setup described above.

## API Documentation

The API provides comprehensive endpoints for managing contacts and events in Nextcloud.

### Events API
The calendar endpoints expose full CRUD operations backed by CalDAV while keeping the interface REST-friendly. All calls require HTTP Basic auth with a Nextcloud account.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/events/{uid}` | Retrieve one event by UID with optional field masking |
| `GET` | `/events` | List events within a time range, sorted chronologically |
| `POST` | `/events` | Create a new event (UID auto-generated if omitted) |
| `PUT` | `/events/{uid}` | Update an existing event in place |
| `DELETE` | `/events/{uid}` | Remove an event permanently |

#### Common query parameters
- `calendar_name` *(optional)* – Target a specific Nextcloud calendar. When omitted the user's default `personal` calendar is used.

#### Read-only options
- `privacy` *(optional bool, defaults to `false`)* – Masks sensitive fields (summary, description, attendees, etc.) at the parsing layer so you can safely display data in public dashboards or agentic workflows. Available only on the `GET /events` and `GET /events/{uid}` endpoints.

#### Example – Fetch masked events within a week
```bash
curl -u alice:secret \
  "http://localhost:13000/events?start_datetime=2025-04-21T00:00:00&end_datetime=2025-04-28T23:59:59&privacy=true"
```

Sample response:
```json
[
  {
    "uid": "550e8400-e29b-41d4-a716-446655440000",
    "summary": "***",
    "start": "2025-04-21T14:00:00",
    "end": "2025-04-21T15:00:00",
    "classification": "PRIVATE"
  }
]
```

#### Notes
- Write operations (POST/PUT/DELETE) always accept the full event payload; masking applies only when reading data.
- All datetime fields must be ISO strings (`YYYY-MM-DDTHH:MM:SS`).
- Responses always include the CalDAV `classification` value so you can map privacy levels in your UI.

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
```

## Contributing
Let me know if you want to participate and how!

## License
**License**: [MIT](https://choosealicense.com/licenses/mit/)
**Author**: harokku999@gmail.com
