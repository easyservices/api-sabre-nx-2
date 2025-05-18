# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""Security utilities for authentication and authorization.

This module provides utility functions for handling security-related operations
such as generating authentication headers for API requests.
"""

import base64

from fastapi import HTTPException, status
import requests
from fastapi.security import HTTPBasicCredentials
from src.nextcloud.config import NEXTCLOUD_BASE_URL
from cachetools import TTLCache

# Cache with max 100 users, 300 seconds (5 min) TTL
auth_cache = TTLCache(maxsize=100, ttl=300)


def cache_key(credentials: HTTPBasicCredentials) -> str:
    return f"{credentials.username}:{credentials.password}"


def authenticate_with_nextcloud(credentials: HTTPBasicCredentials):
    key = cache_key(credentials)

    # Return from cache if available
    if key in auth_cache:
        return auth_cache[key]

    # Authenticate with Nextcloud
    url = f"{NEXTCLOUD_BASE_URL}/ocs/v2.php/cloud/user?format=json"
    headers = {"OCS-APIRequest": "true"}
    response = requests.get(url, auth=(credentials.username, credentials.password), headers=headers)

    if response.status_code == 200:
        user_info = response.json()["ocs"]["data"]
        auth_cache[key] = user_info  # Cache successful auth
        return user_info
    elif response.status_code == 401:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    else:
        raise HTTPException(status_code=500, detail="Nextcloud auth failed")


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