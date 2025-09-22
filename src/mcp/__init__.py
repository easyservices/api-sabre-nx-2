"""Legacy MCP integration retained for agent compatibility.

The API-only deployment does not require this module, but it remains available
for environments that still rely on FastMCP tooling.
"""

from fastmcp import FastMCP
import yaml
import os


def load_config():
    """Load configuration from YAML file."""
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)


config = load_config()
mcp = FastMCP(config["fastmcp"].get("title"), config["fastmcp"].get("description"))

# Import tools after creating the mcp instance to avoid circular imports
from .tools import (
    calculate_bmi,
    get_all_contacts,
)