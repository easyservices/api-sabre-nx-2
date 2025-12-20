# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""Runtime Nextcloud configuration helpers.

Configuration is read on demand so tests and environments can override values
without relying on module import side effects.
"""

from functools import lru_cache
from typing import Dict

from . import load_config


@lru_cache(maxsize=1)
def get_nextcloud_config() -> Dict:
    """Load Nextcloud configuration (cached for the process lifetime)."""
    config = load_config()
    return config.get("nextcloud", {}) if config else {}


def get_nextcloud_base_url() -> str:
    """Return the configured base URL for the Nextcloud instance."""
    return get_nextcloud_config().get("base_url", "https://nextcloud.example.com:8083")


def get_api_proxy_url() -> str:
    """Return the configured API proxy URL (used by tests/CLI)."""
    return get_nextcloud_config().get("api_proxy_url", "http://localhost:1260")


def reset_nextcloud_config_cache() -> None:
    """Clear cached configuration (useful for tests changing env/config)."""
    get_nextcloud_config.cache_clear()
