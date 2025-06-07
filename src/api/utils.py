# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

from fastapi import APIRouter, Depends

from fastapi.security import HTTPBasicCredentials
from src.common import security
from src.models.api_params import StatusQueryParams
from src.common.sec import authenticate_with_nextcloud
from src import logger

# --- Router Definition ---
# We're using the get_user_settings dependency directly in each endpoint
# instead of applying validate_api_key to all routes
router = APIRouter()

@router.get(
    "/status",
    operation_id="get_server_status",
    summary="Get server status",
    description="Check server health and authentication status",
    responses={
        200: {
            "description": "Server is running and authentication is working",
            "content": {
                "application/json": {
                    "example": {"status": "running"}
                }
            },
        },
        401: {
            "description": "Authentication failed",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid credentials"}
                }
            },
        },
        503: {
            "description": "Server or Nextcloud connection issue",
            "content": {
                "application/json": {
                    "example": {"detail": "Nextcloud connection failed"}
                }
            },
        },
    },
    tags=["utils"],
)
async def get_status(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Get the status of the server and verify Nextcloud connectivity.
    
    This endpoint serves as a health check for the API server and validates
    that authentication with the Nextcloud backend is functioning properly.
    
    **Key Features:**
    - Server health verification
    - Nextcloud authentication validation
    - Connection status checking
    - Quick diagnostic endpoint
    
    **Authentication:**
    Requires HTTP Basic Authentication with valid Nextcloud credentials.
    
    **Use Cases:**
    - API health monitoring
    - Authentication troubleshooting
    - Service availability checking
    - Integration testing
    
    **Response:**
    Returns a simple status object indicating the server is operational
    and can successfully authenticate with Nextcloud.
    """
    user_info = authenticate_with_nextcloud(credentials)
    logger.debug(f"User credentials: {user_info}")
    return {"status": "running"}
