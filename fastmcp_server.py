# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Legacy FastMCP Server

Earlier revisions of this project exposed Nextcloud data through a Model Context
Protocol (MCP) server alongside the REST API. The API-only deployment no longer
depends on this component, but the script is kept for teams that still integrate
with MCP-based agents.
"""

import httpx
from src.common.sec import authenticate_with_nextcloud
from src.common import security
from src.mcp import mcp, config
from src.nextcloud.config import NEXTCLOUD_BASE_URL


# Run the server directly with uvicorn when this script is executed
if __name__ == "__main__":

    print(f"Starting legacy {config['fastmcp']['title']} v{config['fastmcp']['version']}")
    print(f"Legacy MCP server on http://{config['fastmcp']['host']}:{config['fastmcp']['port']}/mcp")
    print("API with path /mcp for Streamable HTTP transport, and /sse for SSE transport")
    print(f"Primary REST API server on {NEXTCLOUD_BASE_URL}")
    mcp.run(
        transport="streamable-http",
        host=config['fastmcp']['host'],
        port=config['fastmcp']['port'],
        log_level=config['fastmcp']['log_level'],
    )

