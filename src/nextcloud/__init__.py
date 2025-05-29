# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

import os
import yaml


def load_config():
    """Load configuration from YAML file."""
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)

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