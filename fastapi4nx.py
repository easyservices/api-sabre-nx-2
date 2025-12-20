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
Application settings are loaded from validated environment variables
via a centralized Pydantic Settings object (.env supported).

**Usage:**
Run this file directly to start the development server, or deploy using
a production WSGI server like Gunicorn or Uvicorn for production environments.
"""

from fastapi import FastAPI
from src.api import contacts, events, utils, tasks
from src.api import load_config as load_fastapi_config
import uvicorn
from starlette.middleware.trustedhost import TrustedHostMiddleware
from src.common.add_proxy import CustomProxyHeadersMiddleware
from fastapi_pagination import add_pagination
from src import logger
from src.nextcloud.libs import carddav_client
from src.logging_utils import setup_logging, RequestContextMiddleware
from src.settings import get_settings

def create_app() -> FastAPI:
    """Build the FastAPI application with runtime configuration loading."""
    setup_logging()
    fastapi_config = load_fastapi_config()
    settings = get_settings()

    openapi_tags = [
        {
            "name": "contacts",
            "description": (
                "CardDAV contact operations. Use HTTP Basic Auth for every call. "
                "Responses may include caching hints (`X-Cache`, `X-Cache-TTL`) and always return JSON. "
                "Privacy flag masks sensitive fields. Create/update/delete will invalidate cached list/search results."
            ),
        },
        {
            "name": "events",
            "description": (
                "CalDAV event operations. Basic Auth required. "
                "Read endpoints are cacheable and advertise `X-Cache` / `X-Cache-TTL` headers; writes invalidate caches. "
                "Always send ISO timestamps (YYYY-MM-DDTHH:MM:SS). Calendar name defaults to `personal`."
            ),
        },
        {
            "name": "tasks",
            "description": (
                "CalDAV task (VTODO) operations. Basic Auth required. "
                "Read endpoints are cacheable with `X-Cache` / `X-Cache-TTL`; writes invalidate caches. "
                "Supports due/start dates and percent-complete fields. Calendar name defaults to `personal`."
            ),
        },
        {
            "name": "utils",
            "description": "Utility and health endpoints for readiness/liveness checks.",
        },
    ]

    app = FastAPI(
        title=fastapi_config['fastapi']['title'],
        summary=fastapi_config['fastapi']['summary'],
        description=fastapi_config['fastapi']['description'],
        version=fastapi_config['fastapi']['version'],
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=openapi_tags,
    )

    # Persist config on the app for downstream dependencies/tests
    app.state.fastapi_config = fastapi_config
    app.state.settings = settings
    app.add_middleware(RequestContextMiddleware)

    @app.on_event("startup")
    async def _startup_clients():
        await carddav_client.init_client()

    @app.on_event("shutdown")
    async def _shutdown_clients():
        await carddav_client.close_client()

    # Ajoute d'abord ProxyHeadersMiddleware pour gérer X-Forwarded-*
    app.add_middleware(CustomProxyHeadersMiddleware)

    # (Optionnel) Ajoute TrustedHostMiddleware si tu veux restreindre les hôtes autorisés
    allowed_hosts = fastapi_config['fastapi']['allowed_hosts'] or ["*"]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)

    # Add pagination support to the FastAPI app
    add_pagination(app)

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
    app.include_router(
        tasks.router,
        prefix="/tasks",
        tags=["tasks"],
        responses={401: {"description": "Authentication failed"}},
    )

    logger.info(f"Starting {fastapi_config['fastapi']['title']} v{fastapi_config['fastapi']['version']}")
    logger.info(f"API documentation available at http://{fastapi_config['fastapi']['host']}:{fastapi_config['fastapi']['port']}/docs")
    logger.info(f"ReDoc documentation available at http://{fastapi_config['fastapi']['host']}:{fastapi_config['fastapi']['port']}/redoc")
    logger.info(f"Server status at http://{fastapi_config['fastapi']['host']}:{fastapi_config['fastapi']['port']}/status")

    return app


app = create_app()

# Mount static files directory for serving frontend assets
#app.mount("/static", StaticFiles(directory="static"), name="static")

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
    # Start the FastAPI server with Uvicorn
    cfg = app.state.fastapi_config
    uvicorn.run(
        "fastapi4nx:app",  # Path to the FastAPI app object (filename:variable_name)
        reload=cfg['fastapi']['reload'],             # Enable auto-reload for development
        port=cfg['fastapi']['port'],                 # Port to listen on
        host=cfg['fastapi']['host'],                 # Host to bind to (0.0.0.0 for all interfaces)
        log_level=cfg['fastapi']['log_level'],       # Log level
    )


