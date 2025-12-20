# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

import yaml
import os
from src.common import load_config
from src.common.libs.helpers import UserSettings
from src import logger
from typing import Optional


def _create_users_dict() -> dict[str, UserSettings]:
    """Create users dictionary from environment-driven configuration."""
    config = load_config()
    users = {}
    for username, user_data in config.get('users', {}).items():
        users[username] = UserSettings(
            NEXTCLOUD_USERNAME=user_data['NEXTCLOUD_USERNAME'],
            NEXTCLOUD_PASSWORD=user_data['NEXTCLOUD_PASSWORD'],
            NEXTCLOUD_CALENDAR=user_data.get('NEXTCLOUD_CALENDAR'),
        )
    return users


class UsersSettings:
    """Class to hold user settings for tests only against a Nextcloud server."""
    _users_cache: Optional[dict[str, UserSettings]] = None

    @property
    def USERS(self) -> dict[str, UserSettings]:
        if self._users_cache is None:
            self._users_cache = _create_users_dict()
        return self._users_cache

