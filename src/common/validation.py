# Shared validation utilities for datetime parsing and event/calendar checks.

from datetime import datetime
from typing import Tuple

from fastapi import HTTPException


def parse_iso_datetime(value: str) -> datetime:
    """Parse ISO8601 string; accept trailing Z; raise HTTP 400 on failure."""
    if not value or not str(value).strip():
        raise HTTPException(status_code=400, detail="Datetime value is required")
    candidate = str(value).strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        return datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid datetime format: {value}. Expected ISO 8601") from exc


def validate_time_range(start_str: str, end_str: str, label_prefix: str = "Time range") -> Tuple[datetime, datetime]:
    """Validate that end is after start and both datetimes are compatible."""
    start_dt = parse_iso_datetime(start_str)
    end_dt = parse_iso_datetime(end_str)
    if (start_dt.tzinfo is None) != (end_dt.tzinfo is None):
        raise HTTPException(
            status_code=400,
            detail=f"{label_prefix} start and end must both include a timezone or neither",
        )
    if end_dt <= start_dt:
        raise HTTPException(status_code=400, detail=f"{label_prefix} end time must be after start time")
    return start_dt, end_dt


def validate_event_datetimes(start: str, end: str | None):
    """Validate event start/end ordering and timezone consistency."""
    start_dt = parse_iso_datetime(start)
    end_dt = None
    if end:
        end_dt = parse_iso_datetime(end)
        if (start_dt.tzinfo is None) != (end_dt.tzinfo is None):
            raise HTTPException(
                status_code=400,
                detail="Event start and end must both include a timezone or neither",
            )
        if end_dt <= start_dt:
            raise HTTPException(status_code=400, detail="Event end time must be after start time")
    return start_dt, end_dt


def validate_task_datetimes(start: str | None, due: str | None, label_prefix: str = "Task"):
    """
    Validate task start/due ordering and timezone consistency.

    Allows tasks without a start or due date, but when both are present they must
    share timezone semantics and the due date must not precede the start date.
    """
    start_dt = parse_iso_datetime(start) if start else None
    due_dt = parse_iso_datetime(due) if due else None

    if start_dt and due_dt:
        if (start_dt.tzinfo is None) != (due_dt.tzinfo is None):
            raise HTTPException(
                status_code=400,
                detail=f"{label_prefix} start and due must both include a timezone or neither",
            )
        if due_dt < start_dt:
            raise HTTPException(status_code=400, detail=f"{label_prefix} due time must be on or after start time")

    return start_dt, due_dt
