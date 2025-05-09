# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""Core application package for the src namespace.

This package serves as the root for all src-related modules and subpackages.
It defines constants used throughout the application, including API metadata
and configuration settings.
"""

TITLE_FASTAPI = "Nextcloud FastAPI"
SUMMARY_FASTAPI = (
    "A comprehensive FastAPI application that serves as a backend for Nextcloud, "
    "providing RESTful APIs for contacts and events management with CardDAV/CalDAV integration."
)
DESCRIPTION_FASTAPI = """
This FastAPI application is designed to work with Nextcloud, providing RESTful APIs for managing contacts and events.
It includes the following features:

## Features
- Complete CardDAV integration for contacts management
- Complete CalDAV integration for calendar events management
- HTTP Basic Authentication with Nextcloud credentials
- Model Context Protocol (MCP) server implementation
- SSE (Server-Sent Events) support for real-time updates
- Static file server for frontend assets

## Authentication
All API endpoints require HTTP Basic Authentication with your Nextcloud credentials.

## API Documentation
Detailed API documentation is available in the API.md file and through the Swagger UI at /docs.

## Contacts API
- GET /contacts/ - Get all contacts
- GET /contacts/{uid} - Get a contact by UID
- POST /contacts/ - Create a new contact
- PUT /contacts/{uid} - Update an existing contact
- DELETE /contacts/{uid} - Delete a contact
- POST /contacts/search - Search for contacts

## Events API
- GET /events/{uid} - Get an event by UID
- GET /events/?start_datetime={start}&end_datetime={end} - Get events in a time range
- POST /events/ - Create a new event
- PUT /events/{uid} - Update an existing event
- DELETE /events/{uid} - Delete an event
"""
VERSION_FASTAPI = "0.1.0"

