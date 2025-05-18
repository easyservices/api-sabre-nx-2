# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Nextcloud FastAPI Server

This is the main entry point for the Nextcloud FastAPI application.
It sets up the FastAPI app, includes the API routers, and configures
the Model Context Protocol (MCP) server.

The application provides RESTful APIs for managing Nextcloud contacts and events
using CardDAV and CalDAV protocols.
"""

from fastapi import Depends, FastAPI
from fastapi.security import HTTPBasicCredentials
from fastapi_mcp import FastApiMCP
from src import DESCRIPTION_FASTAPI, SUMMARY_FASTAPI, TITLE_FASTAPI, VERSION_FASTAPI
from src.api import contacts, events
import uvicorn
from starlette.staticfiles import StaticFiles
from src.common.sec import authenticate_with_nextcloud
from src.common import security

# Create FastAPI app instance with metadata
app = FastAPI(
    title=TITLE_FASTAPI,
    summary=SUMMARY_FASTAPI,
    description=DESCRIPTION_FASTAPI,
    version=VERSION_FASTAPI,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)


@app.get("/status", operation_id="status", summary="Get the status of the server", description="Returns the status of the server")
async def get_status(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Get the status of the server.
    
    This endpoint checks if the server is running and if the authentication with Nextcloud is working.
    It requires HTTP Basic Authentication with Nextcloud credentials.
    
    Authentication:
        HTTP Basic Authentication with Nextcloud credentials
    
    Returns:
        dict: A dictionary with the status of the server
        
    Example Response:
        {
            "status": "running"
        }
    """
    user_info = authenticate_with_nextcloud(credentials)
    #print(f"User info: {user_info}")
    return {"status": "running"}

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

# Configure and mount the MCP server
mcp = FastApiMCP(
    app,
    name="Nextcloud MCP Server",
    description="Model Context Protocol server for Nextcloud integration",
    describe_full_response_schema=True,  # Describe the full response JSON-schema instead of just a response example
    describe_all_responses=True,  # Describe all the possible responses instead of just the success (2XX) response
)

# Mount the MCP server to the FastAPI app
mcp.mount()

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
# Generate an MCP server directly from the FastAPI app
#mcp = FastMCP.from_fastapi(app, TITLE_MCP_SERVER, port=1260, host="0.0.0.0", log_level="DEBUG")
# Mount the MCP server's to FastAPI app
#app.mount("/", mcp.sse_app())

# Run the server directly with uvicorn when this script is executed
if __name__ == "__main__":
    print(f"Starting {TITLE_FASTAPI} v{VERSION_FASTAPI}")
    print(f"API documentation available at http://localhost:1260/docs")
    print(f"ReDoc documentation available at http://localhost:1260/redoc")
    
    uvicorn.run(
        "fastapi_server:app",  # Path to the FastAPI app object (filename:variable_name)
        reload=True,           # Enable auto-reload for development
        port=1260,             # Port to listen on
        host="0.0.0.0",        # Host to bind to (0.0.0.0 for all interfaces)
        log_level="info",     # Log level
    )

