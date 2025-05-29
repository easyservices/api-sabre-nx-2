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

from fastmcp import FastMCP
import httpx
from src.common.sec import authenticate_with_nextcloud
from src.common import security
from src.mcp import mcp, config
from src.nextcloud.config import NEXTCLOUD_BASE_URL


# Run the server directly with uvicorn when this script is executed
if __name__ == "__main__":

    print(f"Starting {config['fastmcp']['title']} v{config['fastmcp']['version']}")
    print(f"MCP server on http://{config['fastmcp']['host']}:{config['fastmcp']['port']}/mcp")
    print(f"API with path /mcp for Streamable HTTP transport, and /sse for SSE transport")
    print(f"FastAPI server on {NEXTCLOUD_BASE_URL}")
    mcp.run(
        transport="streamable-http",
        host=config['fastmcp']['host'],
        port=config['fastmcp']['port'],
        log_level=config['fastmcp']['log_level'],
    )

