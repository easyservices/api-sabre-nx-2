# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""Security helpers for authenticating against Nextcloud."""

import asyncio
import base64
import os
import time

import httpx
from fastapi import HTTPException, status
from fastapi.security import HTTPBasicCredentials
from src.nextcloud.config import NEXTCLOUD_BASE_URL
from cachetools import TTLCache
from src import logger

# Cache with max 100 users, 300 seconds (5 min) TTL
auth_cache = TTLCache(maxsize=100, ttl=300)

# Circuit breaker / retry controls (configurable through env vars)
AUTH_TIMEOUT = float(os.getenv("NEXTCLOUD_AUTH_TIMEOUT", "10"))
AUTH_CONNECT_TIMEOUT = float(os.getenv("NEXTCLOUD_AUTH_CONNECT_TIMEOUT", "5"))
AUTH_MAX_RETRIES = int(os.getenv("NEXTCLOUD_AUTH_MAX_RETRIES", "3"))
AUTH_BACKOFF = float(os.getenv("NEXTCLOUD_AUTH_BACKOFF", "0.6"))
AUTH_CIRCUIT_THRESHOLD = int(os.getenv("NEXTCLOUD_AUTH_CIRCUIT_THRESHOLD", "5"))
AUTH_CIRCUIT_RESET = float(os.getenv("NEXTCLOUD_AUTH_CIRCUIT_RESET", "30"))
AUTH_PROXY = os.getenv("NEXTCLOUD_AUTH_PROXY")

_circuit_lock = asyncio.Lock()
_circuit_state = {"failures": 0, "open_until": 0.0}


def cache_key(credentials: HTTPBasicCredentials) -> str:
    return f"{credentials.username}:{credentials.password}"


async def _ensure_circuit_allows_request() -> None:
    """Prevent outbound calls when the breaker is open."""
    async with _circuit_lock:
        now = time.monotonic()
        open_until = _circuit_state.get("open_until", 0.0)
        if open_until and now < open_until:
            raise HTTPException(status_code=503, detail="Nextcloud auth temporarily unavailable")
        if open_until and now >= open_until:
            _circuit_state["open_until"] = 0.0
            _circuit_state["failures"] = 0


async def _record_success() -> None:
    async with _circuit_lock:
        _circuit_state["failures"] = 0
        _circuit_state["open_until"] = 0.0


async def _record_failure() -> None:
    async with _circuit_lock:
        _circuit_state["failures"] += 1
        if _circuit_state["failures"] >= AUTH_CIRCUIT_THRESHOLD:
            _circuit_state["open_until"] = time.monotonic() + AUTH_CIRCUIT_RESET
            _circuit_state["failures"] = 0


async def authenticate_with_nextcloud(credentials: HTTPBasicCredentials):
    """
    Authenticate user credentials against Nextcloud server.
    
    Validates HTTP Basic Authentication credentials by making a request to the
    Nextcloud OCS API. Implements caching to reduce authentication overhead
    for repeated requests with the same credentials.
    
    **Authentication Flow:**
    1. Check if credentials are cached and still valid
    2. If not cached, make OCS API request to Nextcloud
    3. Validate response and extract user information
    4. Cache successful authentication for future requests
    5. Return user information or raise appropriate HTTP exception
    
    **Caching Strategy:**
    - Cache key: combination of username and password
    - TTL: 300 seconds (5 minutes)
    - Max size: 100 concurrent users
    - Automatic expiration and cleanup
    
    **Security Considerations:**
    - Credentials are validated against live Nextcloud user database
    - No local password storage or validation
    - Cache keys use the raw username and password combination stored only in-memory
    - Proper HTTP status codes for different failure scenarios
    
    Args:
        credentials: HTTP Basic Authentication credentials containing username and password
        
    Returns:
        dict: User information from Nextcloud OCS API including user ID and metadata
        
    Raises:
        HTTPException(401): Invalid credentials or authentication failure
        HTTPException(500): Nextcloud server communication error
        
    Example:
        ```python
        from fastapi.security import HTTPBasicCredentials
        
        creds = HTTPBasicCredentials(username="user", password="pass")
        user_info = await authenticate_with_nextcloud(creds)
        logger.debug(f"Authenticated user: {user_info['id']}")
        ```
    """
    key = cache_key(credentials)

    if key in auth_cache:
        return auth_cache[key]

    await _ensure_circuit_allows_request()

    url = f"{NEXTCLOUD_BASE_URL}/ocs/v2.php/cloud/user?format=json"
    headers = {"OCS-APIRequest": "true"}
    timeout = httpx.Timeout(AUTH_TIMEOUT, connect=AUTH_CONNECT_TIMEOUT)
    attempt = 0

    while True:
        attempt += 1
        try:
            client_kwargs = {"timeout": timeout}
            transport = None
            if AUTH_PROXY:
                transport = httpx.AsyncHTTPTransport(proxy=AUTH_PROXY)
                client_kwargs["transport"] = transport
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.get(
                    url,
                    auth=(credentials.username, credentials.password),
                    headers=headers,
                )

            if response.status_code == 200:
                user_info = response.json()["ocs"]["data"]
                auth_cache[key] = user_info
                await _record_success()
                return user_info

            if response.status_code == 401:
                await _record_success()
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid credentials",
                    headers={"WWW-Authenticate": 'Basic realm="Nextcloud"'},
                )

            if response.status_code >= 500:
                await _record_failure()
                if attempt > AUTH_MAX_RETRIES:
                    raise HTTPException(status_code=503, detail="Nextcloud auth temporarily unavailable")
                backoff = AUTH_BACKOFF * attempt
                logger.warning(
                    "Nextcloud auth failed with %s (attempt %s/%s), retrying in %.2fs",
                    response.status_code,
                    attempt,
                    AUTH_MAX_RETRIES,
                    backoff,
                )
                await asyncio.sleep(backoff)
                continue

            await _record_success()
            raise HTTPException(status_code=response.status_code, detail="Nextcloud auth failed")

        except httpx.RequestError as exc:
            await _record_failure()
            if attempt > AUTH_MAX_RETRIES:
                raise HTTPException(status_code=503, detail=f"Nextcloud auth unavailable: {exc}") from exc
            backoff = AUTH_BACKOFF * attempt
            logger.warning(
                "Nextcloud auth request error (attempt %s/%s): %s. Retrying in %.2fs",
                attempt,
                AUTH_MAX_RETRIES,
                exc,
                backoff,
            )
            await asyncio.sleep(backoff)


def gen_basic_auth_header(username: str, password: str) -> str:
    """
    Generate an HTTP Basic Authentication header value.
    
    This function creates a properly formatted Basic Authentication header
    by encoding the username and password according to RFC 7617.
    The process involves:
    1. Combining the username and password with a colon separator
    2. Encoding the combined string to UTF-8 bytes
    3. Base64 encoding the bytes
    4. Prepending "Basic " to the base64-encoded string
    
    Args:
        username: The username for authentication
        password: The password for authentication
        
    Returns:
        A string containing the complete HTTP Basic Authentication header value
        in the format "Basic <base64-encoded-credentials>"
    
    Example:
        >>> gen_basic_auth_header("user", "pass")
        'Basic dXNlcjpwYXNz'
    """
    # Combine username:password
    credentials = f"{username}:{password}"
    # Encode to bytes
    credentials_bytes = credentials.encode('utf-8')
    # Base64 encode the bytes
    base64_credentials_bytes = base64.b64encode(credentials_bytes)
    # Decode back to string
    base64_credentials_string = base64_credentials_bytes.decode('utf-8')
    # Prepend "Basic "
    HTTP_BASIC_AUTH = f"Basic {base64_credentials_string}"
    return HTTP_BASIC_AUTH
