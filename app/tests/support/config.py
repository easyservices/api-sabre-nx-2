# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""Test-specific configuration helpers."""

from dataclasses import dataclass
import os
from src.common.config import UsersSettings
from src.common.sec import gen_basic_auth_header


@dataclass
class TestSettings:
    api_base_url: str
    username: str
    password: str

    def auth_header(self) -> str:
        return gen_basic_auth_header(self.username, self.password)


def get_test_settings(user_key: str = "test4me") -> TestSettings:
    users = UsersSettings()
    user_cfg = users.USERS[user_key]
    return TestSettings(
        api_base_url=os.getenv("NEXTCLOUD_API_PROXY_URL", "http://localhost:13000"),
        username=user_cfg.NEXTCLOUD_USERNAME,
        password=user_cfg.NEXTCLOUD_PASSWORD,
    )
