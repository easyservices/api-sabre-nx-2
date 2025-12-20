# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""Core application package for common helpers.

This package contains common helpers for all functions and classes.
"""

import logging
import os
from fastapi.security import HTTPBasic
import yaml

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv is optional in some environments
    load_dotenv = None


security = HTTPBasic()
logger = logging.getLogger(__name__)


def _load_users_override_from_env():
    """
    Load user credentials overrides from env variables.

    Supports:
    - COMMON_USERS_YAML / COMMON_USERS_JSON: YAML/JSON mapping of users.
    - NEXTCLOUD_USERNAME/NEXTCLOUD_PASSWORD (+ optional NEXTCLOUD_USER_KEY) for quick overrides.
    """
    raw_users = os.getenv("COMMON_USERS_YAML") or os.getenv("COMMON_USERS_JSON")
    if raw_users:
        try:
            users_data = yaml.safe_load(raw_users)
        except yaml.YAMLError as exc:
            raise ValueError("Invalid COMMON_USERS_YAML/JSON content") from exc
        if not isinstance(users_data, dict):
            raise ValueError("COMMON_USERS_YAML/JSON must define a mapping of users")
        return users_data

    username = os.getenv("NEXTCLOUD_USERNAME")
    password = os.getenv("NEXTCLOUD_PASSWORD")
    if username and password:
        user_key = os.getenv("NEXTCLOUD_USER_KEY", "default")
        return {
            user_key: {
                "NEXTCLOUD_USERNAME": username,
                "NEXTCLOUD_PASSWORD": password,
            }
        }

    return None


def _override_common_settings(config):
    """Override YAML values with environment variables if provided."""
    overrides = _load_users_override_from_env()
    if overrides:
        users_cfg = config.setdefault("users", {})
        users_cfg.update(overrides)
    return config


def load_config():
    """Load configuration from environment (.env supported) with optional overrides."""
    if load_dotenv:
        load_dotenv()

    config = {"users": {}}
    return _override_common_settings(config)
