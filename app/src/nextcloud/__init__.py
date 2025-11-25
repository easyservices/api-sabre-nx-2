# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

import os
import yaml


def _get_config_path():
    """Return the config path, allowing NEXTCLOUD_CONFIG_FILE override."""
    default_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    return os.getenv("NEXTCLOUD_CONFIG_FILE", default_path)


def _override_nextcloud_settings(config):
    """Override YAML values with environment variables if provided."""
    nextcloud_cfg = config.setdefault("nextcloud", {})
    env_overrides = {
        "base_url": os.getenv("NEXTCLOUD_BASE_URL"),
    }

    for key, value in env_overrides.items():
        if value is not None:
            nextcloud_cfg[key] = value

    return config


def load_config():
    """Load configuration from YAML file with optional env overrides."""
    config_path = _get_config_path()
    with open(config_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    return _override_nextcloud_settings(config)

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
