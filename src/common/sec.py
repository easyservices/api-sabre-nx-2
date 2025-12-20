# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Security and Authentication Module

Provides HTTP Basic auth validation against Nextcloud using async IO to avoid
blocking the FastAPI event loop. Credentials are cached briefly using a hashed
key so raw passwords are never stored in-memory as cache keys.
"""

import base64
import hashlib
import hmac
import secrets

import httpx
from fastapi import HTTPException, status
from fastapi.security import HTTPBasicCredentials

from src import logger
from src.nextcloud.config import get_nextcloud_base_url
from src.logging_utils import set_user_context
from src.settings import get_settings
from src.common.cache import get_auth_cache

# Cache defaults are conservative to limit credential exposure in memory
AUTH_CACHE_SECRET = secrets.token_hex(32).encode("utf-8")

def _get_auth_timeout() -> float:
    return get_settings().auth_http_timeout

def _get_auth_cache_secret() -> bytes:
    secret = get_settings().auth_cache_secret
    return (secret.encode("utf-8") if secret else AUTH_CACHE_SECRET)

def _auth_cache():
    return get_auth_cache().cache

def cache_key(credentials: HTTPBasicCredentials) -> str:
    """Return a stable, hashed cache key so raw passwords are not stored."""
    raw = f"{credentials.username}:{credentials.password}".encode("utf-8")
    return hmac.new(_get_auth_cache_secret(), raw, hashlib.sha256).hexdigest()


async def authenticate_with_nextcloud(credentials: HTTPBasicCredentials):
    """
    Authenticate user credentials against Nextcloud server asynchronously.

    Uses a short-lived TTL cache keyed by an HMAC of the credentials to avoid
    repeated OCS calls while minimizing time secrets live in memory.
    """
    key = cache_key(credentials)

    # Return from cache if available
    cached = _auth_cache().get(key)
    if cached:
        # Ensure cached auth still populates logging context
        set_user_context(credentials.username)
        return cached

    url = f"{get_nextcloud_base_url()}/ocs/v2.php/cloud/user?format=json"
    headers = {"OCS-APIRequest": "true"}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(_get_auth_timeout())) as client:
            response = await client.get(
                url,
                auth=(credentials.username, credentials.password),
                headers=headers,
            )
    except httpx.RequestError as exc:
        logger.error("Nextcloud auth failed: %s", exc)
        raise HTTPException(status_code=500, detail="Nextcloud auth failed") from exc

    if response.status_code == 200:
        user_info = response.json()["ocs"]["data"]
        _auth_cache()[key] = user_info  # Cache successful auth
        # Record username in log context (never log password)
        set_user_context(credentials.username)
        return user_info
    if response.status_code == 401:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    raise HTTPException(status_code=500, detail="Nextcloud auth failed")


def gen_basic_auth_header(username: str, password: str) -> str:
    """
    Generate an HTTP Basic Authentication header value.

    This function creates a properly formatted Basic Authentication header
    by encoding the username and password according to RFC 7617.
    """
    credentials = f"{username}:{password}"
    base64_credentials_bytes = base64.b64encode(credentials.encode("utf-8"))
    base64_credentials_string = base64_credentials_bytes.decode("utf-8")
    return f"Basic {base64_credentials_string}"
