# Structured logging helpers and request context.

import contextvars
import logging
import logging.config
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Context variables populated per request/auth
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
user_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("user", default=None)


class ContextFilter(logging.Filter):
    """Inject request_id and user from contextvars into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if getattr(record, "request_id", None) is None:
            setattr(record, "request_id", request_id_var.get())
        if getattr(record, "user", None) is None:
            setattr(record, "user", user_var.get())
        return True


class CsvFormatter(logging.Formatter):
    """Emit semicolon-delimited log lines for easy parsing."""

    delimiter = ";"

    @staticmethod
    def _clean(value: Optional[Any], delimiter: str) -> str:
        if value is None:
            return ""
        text = str(value)
        return (
            text.replace("\n", " ")
            .replace("\r", " ")
            .replace(delimiter, " ")
            .strip()
        )

    def format(self, record: logging.LogRecord) -> str:
        parts = [
            datetime.now(timezone.utc).isoformat(),
            record.levelname,
            record.name,
            self._clean(record.getMessage(), self.delimiter),
            self._clean(getattr(record, "request_id", ""), self.delimiter),
            self._clean(getattr(record, "user", ""), self.delimiter),
        ]
        if record.exc_info:
            parts.append(self._clean(self.formatException(record.exc_info), self.delimiter))
        else:
            parts.append("")
        return self.delimiter.join(parts)


def _get_bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def setup_logging():
    """Configure logging with CSV output and mode-aware handlers."""
    reload_enabled = _get_bool_env("FASTAPI_RELOAD", False)
    log_file_env = os.getenv("LOG_FILE")
    # Default to project_root/logs/app.log
    default_log_file = Path(__file__).resolve().parents[1] / "logs" / "app.log"
    log_file = Path(log_file_env) if log_file_env else default_log_file

    handlers: dict[str, dict[str, Any]] = {}
    root_handlers: list[str] = []
    common_handler_config = {
        "formatter": "csv",
        "filters": ["context"],
        "level": "INFO",
    }

    if reload_enabled:
        handlers["console"] = {
            "class": "logging.StreamHandler",
            **common_handler_config,
        }
        root_handlers.append("console")
    else:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(log_file),
            "maxBytes": 5_000_000,
            "backupCount": 5,
            **common_handler_config,
        }
        root_handlers.append("file")

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "filters": {
                "context": {
                    "()": ContextFilter,
                }
            },
            "formatters": {
                "csv": {
                    "()": CsvFormatter,
                }
            },
            "handlers": handlers,
            "root": {
                "handlers": root_handlers,
                "level": "INFO",
            },
        }
    )


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request id to contextvars for the duration of the request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = str(uuid4())
        token_req = request_id_var.set(req_id)
        token_user = user_var.set(None)
        request.state.request_id = req_id
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_var.reset(token_req)
            user_var.reset(token_user)


def set_user_context(username: Optional[str]) -> None:
    """Set the user in contextvars for logging (no password)."""
    user_var.set(username or None)
