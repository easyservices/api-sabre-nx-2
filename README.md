
<!--
Copyright (c) 2025 harokku999@gmail.com
Licensed under the MIT License - https://opensource.org/licenses/MIT
-->

## 🔗 Seamless Integration with Nextcloud through REST/JSON APIs

Our custom-developed solution exposes Nextcloud’s CalDAV and CardDAV interfaces as modern, developer-friendly REST/JSON APIs, enabling seamless integration with virtually any application, regardless of platform or language.

No more dealing with legacy protocols — developers can now access, create, or update calendar events and contact records using simple HTTP requests and standard JSON payloads.

⚙️ Key Benefits:

    📅 REST access to CalDAV: Read, create, update calendar events easily.

    👥 REST access to CardDAV: Manage contacts in a fully interoperable way.

    🔗 Easy integration: Works with any REST-capable system (CRMs, ERPs, bots...).

    🔐 Secure and efficient: Built on top of Nextcloud’s robust auth and permission system.

🚀 Empower your ecosystem

Whether you're developing business automation workflows, personal productivity tools, or AI assistants, this REST/JSON bridge opens up Nextcloud to a whole new world of integrations.

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

The application requires configuration to connect to your Nextcloud instance. Look at the config.example.yaml file in the /src/api and /src/nextcloud directories. Rename them in config.yaml and edit them according to your needs.

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
1. Fork the repository
2. Create your feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push origin feature/your-feature`)
5. Create new Merge Request

## License
**License**: [MIT](https://choosealicense.com/licenses/mit/)
**Author**: harokku999@gmail.com