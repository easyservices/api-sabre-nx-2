# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Timezone utility helpers shared across the project.

Centralizing TZID extraction and application keeps CalDAV parsing/writing
consistent and makes reminder handling easier to reason about.
"""

from datetime import datetime
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def extract_timezone_from_property(prop: Any) -> Optional[str]:
    """
    Extract a timezone identifier from an iCalendar property.

    This checks for an explicit TZID parameter first, then falls back to the
    timezone info already attached to the decoded datetime value.
    """
    if not prop:
        return None

    params = getattr(prop, "params", None)
    if params and "TZID" in params:
        return str(params["TZID"])

    dt_value = getattr(prop, "dt", None)
    if isinstance(dt_value, datetime) and dt_value.tzinfo:
        return timezone_from_datetime(dt_value)

    return None


def timezone_from_datetime(value: datetime) -> Optional[str]:
    """Return a canonical timezone identifier for a datetime."""
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None

    tzinfo = value.tzinfo
    tz_key = getattr(tzinfo, "key", None)
    if tz_key:
        return tz_key
    return tzinfo.tzname(value)


def apply_timezone(value: Optional[datetime], timezone: Optional[str]) -> Optional[datetime]:
    """
    Attach a timezone to a naive datetime when possible.

    If the timezone cannot be resolved, the original datetime is returned.
    """
    if not value or value.tzinfo is not None or not timezone:
        return value

    try:
        return value.replace(tzinfo=ZoneInfo(timezone))
    except (ZoneInfoNotFoundError, ValueError):
        return value
