# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

import os
from copy import deepcopy
from typing import Any, Dict

import yaml

from src import logger


DEFAULT_CONFIG: Dict[str, Dict[str, Any]] = {
    "nextcloud": {
        "base_url": "https://nextcloud.example.com:8083",
        "api_proxy_url": "http://127.0.0.1:8560",
    }
}


def _read_config_file(config_path: str) -> Dict[str, Any]:
    """Read the YAML configuration if it exists, otherwise return an empty dict."""
    try:
        with open(config_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {}
    except FileNotFoundError:
        logger.warning(
            "Nextcloud configuration not found at %s. Falling back to default values.",
            config_path,
        )
    except yaml.YAMLError as exc:
        logger.error(
            "Invalid YAML in Nextcloud configuration %s: %s. Falling back to default values.",
            config_path,
            exc,
        )
    return {}


def _merge_with_defaults(config_data: Dict[str, Any]) -> Dict[str, Any]:
    """Merge the provided configuration dictionary with default values."""
    merged = deepcopy(DEFAULT_CONFIG)
    if "nextcloud" in config_data:
        merged["nextcloud"].update(config_data["nextcloud"] or {})
    return merged


def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file or return default values when missing."""
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    config_data = _read_config_file(config_path)
    return _merge_with_defaults(config_data)

# Error messages
API_ERR_AUTH_FAILED = "Incorrect username or password"
API_ERR_DATE_INVALID = "Invalid format date. Use YYYYMMDDTHHMMSSZ"
API_ERR_AUTH_REFUSED = "Access denied"
API_ERR_CALENDAR_NOT_FOUND = "Calendar not found"
API_ERR_ADDRESSBOOK_NOT_FOUND = "Addressbook not found"
API_ERR_SERVER_ERROR = "Internal Server error"
API_ERR_CONNECTION_ERROR = "Connection error"
API_ERR_SERVER_UNATTENDED_RESPONSE = "Unattended response"
API_ERR_CONFLICT = "Duplicated resource"
