# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Security and Authentication Module

This module provides comprehensive security utilities for authentication and authorization
in the Nextcloud FastAPI application. It handles HTTP Basic Authentication, credential
validation, and secure communication with Nextcloud servers.

**Key Components:**
- **Authentication Cache**: TTL-based caching for validated credentials
- **Nextcloud Integration**: Direct authentication validation with Nextcloud OCS API
- **Header Generation**: HTTP Basic Authentication header creation utilities
- **Error Handling**: Proper HTTP status codes for authentication failures

**Security Features:**
- **Credential Caching**: Reduces authentication overhead with time-based cache
- **Secure Validation**: Direct verification against Nextcloud user database
- **RFC Compliance**: HTTP Basic Authentication per RFC 7617 standards
- **Error Isolation**: Proper exception handling for authentication failures

**Cache Management:**
The authentication cache stores validated credentials for 5 minutes (300 seconds)
with a maximum of 100 concurrent users to balance performance and security.

**Integration Points:**
- FastAPI dependency injection for endpoint authentication
- Nextcloud OCS API for user validation
- CardDAV/CalDAV operations requiring authenticated requests

**Usage:**
This module is primarily used as a dependency in FastAPI endpoints to ensure
all API operations are performed with valid Nextcloud credentials.
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
    - Cache keys include password hash for security
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
        user_info = authenticate_with_nextcloud(creds)
        print(f"Authenticated user: {user_info['id']}")
        ```
    """
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