# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""Core application package for common helpers.

This package contains common helpers for all functions and classes.
"""

import os
from copy import deepcopy
from typing import Any, Dict

from fastapi.security import HTTPBasic
import yaml

from src import logger


security = HTTPBasic()

DEFAULT_CONFIG: Dict[str, Dict[str, Any]] = {
    "users": {
        "test4me": {
            "NEXTCLOUD_USERNAME": "test4me",
            "NEXTCLOUD_PASSWORD": "changeme",
        }
    }
}


def _read_config_file(config_path: str) -> Dict[str, Any]:
    """Read the YAML configuration if present, otherwise return an empty dict."""
    try:
        with open(config_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {}
    except FileNotFoundError:
        logger.warning(
            "Common configuration not found at %s. Falling back to default values.",
            config_path,
        )
    except yaml.YAMLError as exc:
        logger.error(
            "Invalid YAML in common configuration %s: %s. Falling back to default values.",
            config_path,
            exc,
        )
    return {}


def _merge_with_defaults(config_data: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(DEFAULT_CONFIG)
    if "users" in config_data:
        for username, settings in (config_data["users"] or {}).items():
            merged.setdefault("users", {})[username] = settings
    return merged


def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file or return default values when missing."""
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    config_data = _read_config_file(config_path)
    return _merge_with_defaults(config_data)
