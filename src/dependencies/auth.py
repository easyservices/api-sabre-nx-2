# FastAPI dependency to authenticate and set user context.

from dataclasses import dataclass
from fastapi import Depends
from fastapi.security import HTTPBasicCredentials

from src.common import security
from src.common.sec import authenticate_with_nextcloud


@dataclass
class AuthContext:
    credentials: HTTPBasicCredentials
    user_info: dict


async def authenticated_user(
    credentials: HTTPBasicCredentials = Depends(security),
) -> AuthContext:
    user_info = await authenticate_with_nextcloud(credentials)
    return AuthContext(credentials=credentials, user_info=user_info)
