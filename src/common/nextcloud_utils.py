from typing import Awaitable, Callable, TypeVar

from fastapi import HTTPException

from src import logger

T = TypeVar("T")


async def run_nextcloud_call(action: str, fn: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
    """
    Run a Nextcloud call and normalize error handling.

    - Propagates HTTPException untouched.
    - Converts ValueError to HTTP 400.
    - Wraps other exceptions as HTTP 503 with a consistent message.
    """
    try:
        return await fn(*args, **kwargs)
    except HTTPException:
        raise
    except ValueError as exc:
        msg = f"ValueError: {exc}"
        logger.error(msg)
        raise HTTPException(status_code=400, detail=msg) from exc
    except Exception as exc:
        msg = f"Could not {action}: {exc}"
        logger.error(msg)
        raise HTTPException(status_code=503, detail=msg) from exc
