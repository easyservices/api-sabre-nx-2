# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Nextcloud FastAPI Server

This is the main entry point for the Nextcloud FastAPI application that provides
a comprehensive RESTful API interface for managing Nextcloud contacts and calendar events.

**Architecture Overview:**
The application is built using FastAPI and implements CardDAV/CalDAV protocols to
communicate with Nextcloud servers. It provides a modern REST API layer on top
of the traditional WebDAV-based protocols.

**Key Features:**
- **Contact Management**: Full CRUD operations for CardDAV contacts
- **Event Management**: Complete calendar event handling via CalDAV
- **Authentication**: HTTP Basic Authentication with Nextcloud credentials
- **Real-time Data**: Direct integration with Nextcloud for live data access
- **OpenAPI Documentation**: Comprehensive API documentation with Swagger UI
- **Static File Serving**: Frontend asset delivery capabilities

**API Endpoints:**
- `/contacts/*` - Contact management operations
- `/events/*` - Calendar event operations
- `/utils/status` - Server health and status checking
- `/docs` - Interactive API documentation (Swagger UI)
- `/redoc` - Alternative API documentation (ReDoc)

**Protocol Support:**
- **CardDAV**: RFC 6352 compliant contact synchronization
- **CalDAV**: RFC 4791 compliant calendar synchronization
- **HTTP Basic Auth**: RFC 7617 authentication mechanism

**Configuration:**
Application settings are loaded from YAML configuration files that define
server parameters, connection details, and operational settings.

**Usage:**
Run this file directly to start the development server, or deploy using
a production WSGI server like Gunicorn or Uvicorn for production environments.
"""

from fastapi import Depends, FastAPI
from fastmcp import FastMCP
from fastapi.security import HTTPBasicCredentials
from src.api import contacts, events, utils
from src.api import load_config as load_fastapi_config
import uvicorn
from starlette.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from src.common.add_proxy import CustomProxyHeadersMiddleware
from src.common.sec import authenticate_with_nextcloud
from src.common import security

# Load configuration
fastapi_config = load_fastapi_config()

# Create FastAPI app instance with metadata
app = FastAPI(
    title=fastapi_config['fastapi']['title'],
    summary=fastapi_config['fastapi']['summary'],
    description=fastapi_config['fastapi']['description'],
    version=fastapi_config['fastapi']['version'],
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Ajoute d'abord ProxyHeadersMiddleware pour gérer X-Forwarded-*
app.add_middleware(CustomProxyHeadersMiddleware)

# (Optionnel) Ajoute TrustedHostMiddleware si tu veux restreindre les hôtes autorisés
app.add_middleware(TrustedHostMiddleware, allowed_hosts=fastapi_config['fastapi']['allowed_hosts'])


# Add utility endpoints for health checks and other utility functions
app.include_router(
    utils.router,
    prefix="/utils",
    tags=["utils"],
    responses={401: {"description": "Authentication failed"}},
)

# Add Nextcloud APIs with appropriate prefixes and tags for OpenAPI documentation
app.include_router(
    contacts.router,
    prefix="/contacts",
    tags=["contacts"],
    responses={401: {"description": "Authentication failed"}},
)

app.include_router(
    events.router,
    prefix="/events",
    tags=["events"],
    responses={401: {"description": "Authentication failed"}},
)

# Mount static files directory for serving frontend assets
app.mount("/static", StaticFiles(directory="static"), name="static")

#@app.get("/")
#async def read_root_endpoint():
#    """Redirect to Swagger API documentation as an HTML file"""
#    from fastapi.responses import RedirectResponse
#    return RedirectResponse(url="/docs")

    
# deactivate this to disable the API key validation for these endpoints
"""
@app.get("/docs")
async def get_documentation(username: str = Depends(validate_api_key)):
    return get_swagger_ui_html(openapi_url="/openapi.json", title="docs")


@app.get("/openapi.json")
async def openapi(username: str = Depends(validate_api_key)):
    return get_openapi(title = "FastAPI", version="0.1.0", routes=app.routes)
"""


# Run the server directly with uvicorn when this script is executed
if __name__ == "__main__":
    print(f"Starting {fastapi_config['fastapi']['title']} v{fastapi_config['fastapi']['version']}")
    print(f"API documentation available at http://{fastapi_config['fastapi']['host']}:{fastapi_config['fastapi']['port']}/docs")
    print(f"ReDoc documentation available at http://{fastapi_config['fastapi']['host']}:{fastapi_config['fastapi']['port']}/redoc")
    print(f"Server status at http://{fastapi_config['fastapi']['host']}:{fastapi_config['fastapi']['port']}/status")
    uvicorn.run(
        "fastapi_server:app",  # Path to the FastAPI app object (filename:variable_name)
        reload=fastapi_config['fastapi']['reload'],             # Enable auto-reload for development
        port=fastapi_config['fastapi']['port'],                 # Port to listen on
        host=fastapi_config['fastapi']['host'],                 # Host to bind to (0.0.0.0 for all interfaces)
        log_level=fastapi_config['fastapi']['log_level'],       # Log level
    )


