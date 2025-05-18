
<!--
Copyright (c) 2025 harokku999@gmail.com
Licensed under the MIT License - https://opensource.org/licenses/MIT
-->

## 🔗 Seamless Integration with Nextcloud through REST/JSON APIs

We are proud to introduce a powerful extension for Nextcloud that revolutionizes how applications interact with its core calendaring and contact services.

Our custom-developed solution exposes Nextcloud’s CalDAV and CardDAV interfaces as modern, developer-friendly REST/JSON APIs, enabling seamless integration with virtually any application, regardless of platform or language.

No more dealing with legacy protocols — developers can now access, create, or update calendar events and contact records using simple HTTP requests and standard JSON payloads.

But that's not all.

This platform also supports MCP (Message-Centric Protocol) mode using Server-Sent Events (SSE), making it natively compatible with intelligent agents and AI-driven automation tools. Real-time updates, continuous event streams, and smart synchronization capabilities are now at your fingertips.
⚙️ Key Benefits:

    📅 REST access to CalDAV: Read, create, update calendar events easily.

    👥 REST access to CardDAV: Manage contacts in a fully interoperable way.

    ⚡ AI/Agent-ready: SSE support for live data streams via MCP.

    🔗 Easy integration: Works with any REST-capable system (CRMs, ERPs, bots...).

    🔐 Secure and efficient: Built on top of Nextcloud’s robust auth and permission system.

🚀 Empower your ecosystem

Whether you're developing business automation workflows, personal productivity tools, or AI assistants, this REST/JSON bridge opens up Nextcloud to a whole new world of integrations.

## Features

- REST API for contacts and events management
- Comprehensive CardDAV/CalDAV integration with Nextcloud
- Model Context Protocol (MCP) server implementation
- SSE (Server-Sent Events) support for real-time updates
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

The application requires configuration to connect to your Nextcloud instance. The main configuration settings are:

1. Nextcloud and API PROXY Base URL: Set in `src/nextcloud/config.example.py`
2. Copy and rename `src/nextcloud/config.example.py` to `src/nextcloud/config.py`


Example configuration:
```python
# In `src/nextcloud/config.py`
NEXTCLOUD_BASE_URL = "https://nextcloud.example.com:8083"
API_BASE_PROXY_URL = "https://api.nextcloud.example.com:8080"
```

## Usage

Start the FastAPI server:
```bash
uvicorn fastapi_server:app --reload --port <your port> --host 0.0.0.0
```

Or run directly using the script:
```bash
python fastapi_server.py
```

The server will be available at `http://localhost:<your port>` with the following endpoints:
- API Documentation: `http://localhost:<your port>/docs`
- Contacts API: `http://localhost:<your port>/contacts`
- Events API: `http://localhost:<your port>/events`
- Status: `http://localhost:<your port>/status`

## API Documentation

The API provides comprehensive endpoints for managing contacts and events in Nextcloud. Below are the main endpoints with example requests and responses.

### Authentication

All API endpoints require HTTP Basic Authentication with your Nextcloud credentials.

```
Authorization: Basic base64(username:password)
```

### Contacts API

#### Get All Contacts

```
GET /contacts/
```

Example Response:
```json
[
  {
    "uid": "550e8400-e29b-41d4-a716-446655440000",
    "full_name": "John Doe",
    "vcs_uri": "https://nextcloud.example.com/remote.php/dav/addressbooks/users/username/contacts/550e8400-e29b-41d4-a716-446655440000.vcf",
    "emails": [
      {
        "tag": "work",
        "email": "john.doe@example.com"
      }
    ],
    "phones": [
      {
        "tag": "cell",
        "number": "+1-555-123-4567"
      }
    ],
    "addresses": [
      {
        "tag": "home",
        "street": "123 Main St",
        "city": "Anytown",
        "state": "CA",
        "postal_code": "12345",
        "country": "USA"
      }
    ],
    "birthday": "1980-01-01",
    "notes": "Project manager",
    "groups": ["friends", "work"]
  }
]
```

#### Get Contact by UID

```
GET /contacts/{uid}
```

Example Response:
```json
{
  "uid": "550e8400-e29b-41d4-a716-446655440000",
  "full_name": "John Doe",
  "vcs_uri": "https://nextcloud.example.com/remote.php/dav/addressbooks/users/username/contacts/550e8400-e29b-41d4-a716-446655440000.vcf",
  "emails": [
    {
      "tag": "work",
      "email": "john.doe@example.com"
    }
  ],
  "phones": [
    {
      "tag": "cell",
      "number": "+1-555-123-4567"
    }
  ],
  "addresses": [
    {
      "tag": "home",
      "street": "123 Main St",
      "city": "Anytown",
      "state": "CA",
      "postal_code": "12345",
      "country": "USA"
    }
  ],
  "birthday": "1980-01-01",
  "notes": "Project manager",
  "groups": ["friends", "work"]
}
```

#### Create Contact

```
POST /contacts/
```

Example Request:
```json
{
  "uid": "550e8400-e29b-41d4-a716-446655440000",
  "full_name": "John Doe",
  "emails": [
    {
      "tag": "work",
      "email": "john.doe@example.com"
    }
  ],
  "phones": [
    {
      "tag": "cell",
      "number": "+1-555-123-4567"
    }
  ],
  "addresses": [
    {
      "tag": "home",
      "street": "123 Main St",
      "city": "Anytown",
      "state": "CA",
      "postal_code": "12345",
      "country": "USA"
    }
  ],
  "birthday": "1980-01-01",
  "notes": "Project manager",
  "groups": ["friends", "work"]
}
```

Example Response:
```json
{
  "uid": "550e8400-e29b-41d4-a716-446655440000",
  "full_name": "John Doe",
  "vcs_uri": "https://nextcloud.example.com/remote.php/dav/addressbooks/users/username/contacts/550e8400-e29b-41d4-a716-446655440000.vcf",
  "emails": [
    {
      "tag": "work",
      "email": "john.doe@example.com"
    }
  ],
  "phones": [
    {
      "tag": "cell",
      "number": "+1-555-123-4567"
    }
  ],
  "addresses": [
    {
      "tag": "home",
      "street": "123 Main St",
      "city": "Anytown",
      "state": "CA",
      "postal_code": "12345",
      "country": "USA"
    }
  ],
  "birthday": "1980-01-01",
  "notes": "Project manager",
  "groups": ["friends", "work"]
}
```

#### Update Contact

```
PUT /contacts/{uid}
```

Example Request:
```json
{
  "uid": "550e8400-e29b-41d4-a716-446655440000",
  "full_name": "John Doe Updated",
  "emails": [
    {
      "tag": "work",
      "email": "john.doe.updated@example.com"
    }
  ],
  "phones": [
    {
      "tag": "cell",
      "number": "+1-555-123-4567"
    }
  ],
  "addresses": [
    {
      "tag": "home",
      "street": "123 Main St",
      "city": "Anytown",
      "state": "CA",
      "postal_code": "12345",
      "country": "USA"
    }
  ],
  "birthday": "1980-01-01",
  "notes": "Project manager - updated",
  "groups": ["friends", "work", "vip"]
}
```

Example Response:
```json
{
  "uid": "550e8400-e29b-41d4-a716-446655440000",
  "full_name": "John Doe Updated",
  "vcs_uri": "https://nextcloud.example.com/remote.php/dav/addressbooks/users/username/contacts/550e8400-e29b-41d4-a716-446655440000.vcf",
  "emails": [
    {
      "tag": "work",
      "email": "john.doe.updated@example.com"
    }
  ],
  "phones": [
    {
      "tag": "cell",
      "number": "+1-555-123-4567"
    }
  ],
  "addresses": [
    {
      "tag": "home",
      "street": "123 Main St",
      "city": "Anytown",
      "state": "CA",
      "postal_code": "12345",
      "country": "USA"
    }
  ],
  "birthday": "1980-01-01",
  "notes": "Project manager - updated",
  "groups": ["friends", "work", "vip"]
}
```

#### Delete Contact

```
DELETE /contacts/{uid}
```

Response: 204 No Content

#### Search Contacts

```
POST /contacts/search
```

Example Request:
```json
{
  "full_name": "John",
  "email": "example.com",
  "search_type": "anyof"
}
```

Example Response:
```json
[
  {
    "uid": "550e8400-e29b-41d4-a716-446655440000",
    "full_name": "John Doe",
    "vcs_uri": "https://nextcloud.example.com/remote.php/dav/addressbooks/users/username/contacts/550e8400-e29b-41d4-a716-446655440000.vcf",
    "emails": [
      {
        "tag": "work",
        "email": "john.doe@example.com"
      }
    ],
    "phones": [
      {
        "tag": "cell",
        "number": "+1-555-123-4567"
      }
    ],
    "addresses": [
      {
        "tag": "home",
        "street": "123 Main St",
        "city": "Anytown",
        "state": "CA",
        "postal_code": "12345",
        "country": "USA"
      }
    ],
    "birthday": "1980-01-01",
    "notes": "Project manager",
    "groups": ["friends", "work"]
  }
]
```

### Events API

#### Get Event by UID

```
GET /events/{uid}
```

Example Response:
```json
{
  "uid": "550e8400-e29b-41d4-a716-446655440000",
  "summary": "Team Meeting",
  "description": "Weekly team sync-up",
  "location": "Conference Room A",
  "url": "https://nextcloud.example.com/remote.php/dav/calendars/username/personal/550e8400-e29b-41d4-a716-446655440000.ics",
  "start": "2025-04-21T14:00:00",
  "end": "2025-04-21T15:00:00",
  "all_day": false,
  "created": "2025-04-01T10:00:00",
  "last_modified": "2025-04-01T10:00:00",
  "status": "CONFIRMED",
  "organizer": "organizer@example.com",
  "categories": ["MEETING", "WORK"],
  "attendees": [
    {
      "email": "john.doe@example.com",
      "name": "John Doe",
      "role": "REQ-PARTICIPANT",
      "status": "ACCEPTED",
      "type": "INDIVIDUAL"
    }
  ],
  "reminders": [
    {
      "type": "DISPLAY",
      "trigger": "-PT15M",
      "description": "Reminder: Team Meeting"
    }
  ],
  "recurrence": "FREQ=WEEKLY;BYDAY=MO",
  "recurrence_id": null
}
```

#### Get Events by Time Range

```
GET /events/?start_datetime=2025-04-21T00:00:00&end_datetime=2025-04-28T23:59:59
```

Example Response:
```json
[
  {
    "uid": "550e8400-e29b-41d4-a716-446655440000",
    "summary": "Team Meeting",
    "description": "Weekly team sync-up",
    "location": "Conference Room A",
    "url": "https://nextcloud.example.com/remote.php/dav/calendars/username/personal/550e8400-e29b-41d4-a716-446655440000.ics",
    "start": "2025-04-21T14:00:00",
    "end": "2025-04-21T15:00:00",
    "all_day": false,
    "created": "2025-04-01T10:00:00",
    "last_modified": "2025-04-01T10:00:00",
    "status": "CONFIRMED",
    "organizer": "organizer@example.com",
    "categories": ["MEETING", "WORK"],
    "attendees": [
      {
        "email": "john.doe@example.com",
        "name": "John Doe",
        "role": "REQ-PARTICIPANT",
        "status": "ACCEPTED",
        "type": "INDIVIDUAL"
      }
    ],
    "reminders": [
      {
        "type": "DISPLAY",
        "trigger": "-PT15M",
        "description": "Reminder: Team Meeting"
      }
    ],
    "recurrence": "FREQ=WEEKLY;BYDAY=MO",
    "recurrence_id": null
  }
]
```

#### Create Event

```
POST /events/
```

Example Request:
```json
{
  "summary": "Team Meeting",
  "description": "Weekly team sync-up",
  "location": "Conference Room A",
  "start": "2025-04-21T14:00:00",
  "end": "2025-04-21T15:00:00",
  "all_day": false,
  "status": "CONFIRMED",
  "categories": ["MEETING", "WORK"],
  "attendees": [
    {
      "email": "john.doe@example.com",
      "name": "John Doe",
      "role": "REQ-PARTICIPANT"
    }
  ],
  "reminders": [
    {
      "type": "DISPLAY",
      "trigger": "-PT15M",
      "description": "Reminder: Team Meeting"
    }
  ]
}
```

Example Response:
```json
{
  "uid": "550e8400-e29b-41d4-a716-446655440000",
  "summary": "Team Meeting",
  "description": "Weekly team sync-up",
  "location": "Conference Room A",
  "url": "https://nextcloud.example.com/remote.php/dav/calendars/username/personal/550e8400-e29b-41d4-a716-446655440000.ics",
  "start": "2025-04-21T14:00:00",
  "end": "2025-04-21T15:00:00",
  "all_day": false,
  "created": "2025-04-01T10:00:00",
  "last_modified": "2025-04-01T10:00:00",
  "status": "CONFIRMED",
  "organizer": "organizer@example.com",
  "categories": ["MEETING", "WORK"],
  "attendees": [
    {
      "email": "john.doe@example.com",
      "name": "John Doe",
      "role": "REQ-PARTICIPANT",
      "status": "NEEDS-ACTION",
      "type": "INDIVIDUAL"
    }
  ],
  "reminders": [
    {
      "type": "DISPLAY",
      "trigger": "-PT15M",
      "description": "Reminder: Team Meeting"
    }
  ],
  "recurrence": null,
  "recurrence_id": null
}
```

#### Update Event

```
PUT /events/{uid}
```

Example Request:
```json
{
  "uid": "550e8400-e29b-41d4-a716-446655440000",
  "summary": "Updated Team Meeting",
  "description": "Weekly team sync-up with updated agenda",
  "location": "Conference Room B",
  "start": "2025-04-21T15:00:00",
  "end": "2025-04-21T16:00:00",
  "all_day": false,
  "status": "CONFIRMED",
  "categories": ["MEETING", "WORK", "UPDATED"],
  "attendees": [
    {
      "email": "john.doe@example.com",
      "name": "John Doe",
      "role": "REQ-PARTICIPANT"
    },
    {
      "email": "jane.smith@example.com",
      "name": "Jane Smith",
      "role": "OPT-PARTICIPANT"
    }
  ]
}
```

Example Response:
```json
{
  "uid": "550e8400-e29b-41d4-a716-446655440000",
  "summary": "Updated Team Meeting",
  "description": "Weekly team sync-up with updated agenda",
  "location": "Conference Room B",
  "url": "https://nextcloud.example.com/remote.php/dav/calendars/username/personal/550e8400-e29b-41d4-a716-446655440000.ics",
  "start": "2025-04-21T15:00:00",
  "end": "2025-04-21T16:00:00",
  "all_day": false,
  "created": "2025-04-01T10:00:00",
  "last_modified": "2025-04-01T11:00:00",
  "status": "CONFIRMED",
  "organizer": "organizer@example.com",
  "categories": ["MEETING", "WORK", "UPDATED"],
  "attendees": [
    {
      "email": "john.doe@example.com",
      "name": "John Doe",
      "role": "REQ-PARTICIPANT",
      "status": "NEEDS-ACTION",
      "type": "INDIVIDUAL"
    },
    {
      "email": "jane.smith@example.com",
      "name": "Jane Smith",
      "role": "OPT-PARTICIPANT",
      "status": "NEEDS-ACTION",
      "type": "INDIVIDUAL"
    }
  ],
  "reminders": [
    {
      "type": "DISPLAY",
      "trigger": "-PT15M",
      "description": "Reminder: Updated Team Meeting"
    }
  ],
  "recurrence": null,
  "recurrence_id": null
}
```

#### Delete Event

```
DELETE /events/{uid}
```

Response: 204 No Content

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

## Project Structure
```
├── fastapi_server.py     # Main FastAPI application entry point
├── requirements.txt      # Python dependencies
├── src/                  # Source code
│   ├── __init__.py       # Package initialization and constants
│   ├── api/              # FastAPI endpoints
│   │   ├── contacts.py   # Contacts API endpoints
│   │   └── events.py     # Events API endpoints
│   ├── common/           # Shared utilities
│   │   ├── config.py     # Configuration handling
│   │   └── sec.py        # Security and authentication
│       └── libs/         # Helper libraries
│   ├── models/           # Pydantic models
│   │   ├── contact.py    # Contact data models
│   │   └── event.py      # Event data models
│   └── nextcloud/        # Nextcloud integration
│       ├── contacts.py   # CardDAV client for contacts
│       ├── events.py     # CalDAV client for events
│       ├── config.py     # Settings for Nextcloud URL
│       └── libs/         # Helper libraries for DAV protocols
├── static/               # Static assets
└── tests/                # Test cases
```

## Contributing
1. Fork the repository
2. Create your feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Create new Merge Request

## License
**License**: [MIT](https://choosealicense.com/licenses/mit/)
**Author**: harokku999@gmail.com