
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
python fastapi_server.py
```

The server will be available at `http://localhost:<your port>` with the following endpoints:
- API Documentation: `http://localhost:<your port>/docs`
- Contacts API: `http://localhost:<your port>/contacts`
- Events API: `http://localhost:<your port>/events`
- Status: `http://localhost:<your port>/status`

## API Documentation

The API provides comprehensive endpoints for managing contacts and events in Nextcloud.

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
