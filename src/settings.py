# Centralized application settings with validation.

from functools import lru_cache
from typing import List, Optional, cast

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated settings loaded from environment (.env supported)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_prefix="",
        str_strip_whitespace=True,
    )

    # FastAPI
    fastapi_title: str = Field(default="Nextcloud FastAPI", alias="FASTAPI_TITLE")
    fastapi_summary: str = Field(default="REST wrapper around Nextcloud CardDAV/CalDAV", alias="FASTAPI_SUMMARY")
    fastapi_description: str = Field(default="", alias="FASTAPI_DESCRIPTION")
    fastapi_version: str = Field(default="0.3.0", alias="FASTAPI_VERSION")
    fastapi_host: str = Field(default="0.0.0.0", alias="FASTAPI_HOST")
    fastapi_port: int = Field(default=1265, alias="FASTAPI_PORT")
    fastapi_reload: bool = Field(default=False, alias="FASTAPI_RELOAD")
    fastapi_log_level: str = Field(default="info", alias="FASTAPI_LOG_LEVEL")
    fastapi_allowed_hosts_raw: str = Field(default="*", alias="FASTAPI_ALLOWED_HOSTS")

    # Nextcloud
    nextcloud_internet_url: AnyHttpUrl = Field(
        default=cast(AnyHttpUrl, "https://nextcloud.example.com:8083"), alias="NEXTCLOUD_INTERNET_URL"
    )
    nextcloud_intranet_url: AnyHttpUrl = Field(
        default=cast(AnyHttpUrl, "http://localhost:8560"), alias="NEXTCLOUD_INTRANET_URL"
    )

    # Auth/cache settings
    auth_cache_ttl: int = Field(default=120, alias="AUTH_CACHE_TTL")
    auth_cache_size: int = Field(default=100, alias="AUTH_CACHE_SIZE")
    auth_http_timeout: float = Field(default=10.0, alias="AUTH_HTTP_TIMEOUT")
    auth_cache_secret: Optional[str] = Field(default=None, alias="AUTH_CACHE_SECRET")

    @field_validator("auth_cache_ttl", "auth_cache_size")
    @classmethod
    def ensure_positive(cls, value):
        if value <= 0:
            raise ValueError("Cache TTL/size must be positive")
        return value

    @staticmethod
    def _split_hosts(raw: str) -> List[str]:
        if raw is None:
            return []
        raw_str = str(raw).strip()
        if not raw_str:
            return []
        if raw_str == "*":
            return ["*"]
        return [host.strip() for host in raw_str.split(",") if host.strip()]

    @property
    def fastapi_dict(self) -> dict:
        return {
            "title": self.fastapi_title,
            "summary": self.fastapi_summary,
            "description": self.fastapi_description,
            "version": self.fastapi_version,
            "host": self.fastapi_host,
            "port": self.fastapi_port,
            "reload": self.fastapi_reload,
            "log_level": self.fastapi_log_level,
            "allowed_hosts": self._split_hosts(self.fastapi_allowed_hosts_raw),
        }

    @property
    def nextcloud_dict(self) -> dict:
        return {
            "base_url": str(self.nextcloud_internet_url),
            "api_proxy_url": str(self.nextcloud_intranet_url),
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
