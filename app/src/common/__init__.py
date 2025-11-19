# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""Core application package for common helpers.

This package contains common helpers for all functions and classes.
"""

import logging
import os
from fastapi.security import HTTPBasic
import yaml


security = HTTPBasic()
logger = logging.getLogger(__name__)


def _get_config_path():
    """Return the config path, allowing COMMON_CONFIG_FILE override."""
    default_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    return os.getenv("COMMON_CONFIG_FILE", default_path)


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
    """Load configuration from YAML file with optional env overrides."""
    config_path = _get_config_path()
    with open(config_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    return _override_common_settings(config)
