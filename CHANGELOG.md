# Nextcloud FastAPI v0.1.0

## REST/JSON Bridge for Nextcloud CalDAV and CardDAV

This initial release provides a modern REST API layer for Nextcloud's calendar and contacts services, enabling seamless integration with any application using standard HTTP requests and JSON payloads.

### Features
- REST API for Nextcloud contacts (CardDAV) and events (CalDAV)
- HTTP Basic Authentication with Nextcloud credentials
- Model Context Protocol (MCP) server with SSE support
- Comprehensive API documentation via Swagger UI
- Complete test suite for API validation

This bridge simplifies integration with Nextcloud by eliminating the need to work directly with DAV protocols, making development faster and more accessible across all platforms and languages.