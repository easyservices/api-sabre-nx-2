# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

import yaml
import os
from src.common import load_config
from src.common.libs.helpers import UserSettings


def _create_users_dict() -> dict[str, UserSettings]:
    """Create users dictionary from YAML configuration."""
    config = load_config()
    users = {}
    for username, user_data in config['users'].items():
        users[username] = UserSettings(
            NEXTCLOUD_USERNAME=user_data['NEXTCLOUD_USERNAME'],
            NEXTCLOUD_PASSWORD=user_data['NEXTCLOUD_PASSWORD']
        )
    return users


class UsersSettings:
    """Class to hold user settings for tests only against a Nextcloud server."""
    USERS: dict[str, UserSettings] = _create_users_dict()



