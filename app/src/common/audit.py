# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""Simple JSONL audit logging helpers."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

AUDIT_LOG_PATH = Path(os.getenv("FASTAPI_AUDIT_LOG", "app/logs/audit.log"))


def _write_entry(line: str) -> None:
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(line + "\n")


async def record_change(
    resource_type: str,
    uid: str,
    action: str,
    before: Optional[Dict[str, Any]],
    after: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Persist a JSON line describing a mutation for later debugging/rollbacks.

    Args:
        resource_type: Logical resource name (e.g., "contact" or "event").
        uid: Resource UID.
        action: Mutation type ("create", "update", "delete").
        before: Previous payload snapshot (if available).
        after: New payload snapshot (if applicable).
    """
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "resource": resource_type,
        "action": action,
        "uid": uid,
        "before": before,
        "after": after,
    }
    line = json.dumps(entry, default=str)
    await asyncio.to_thread(_write_entry, line)
