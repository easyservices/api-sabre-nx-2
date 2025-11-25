# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Utility helpers for reminder parsing, normalization, and serialization.

Keeping this logic centralized ensures both the API surface and the CalDAV
integration stay in sync when reminder behavior evolves.
"""

from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Any, Dict, Optional, Tuple, TYPE_CHECKING
import re

from src.common.timezones import (
    apply_timezone,
    extract_timezone_from_property,
    timezone_from_datetime,
)

if TYPE_CHECKING:
    from src.models.event import Reminder


def normalize_reminder_input(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize reminder payloads regardless of whether clients send the legacy
    trigger format or the new structured schema.
    """
    normalized = data.copy()
    legacy_trigger = normalized.pop("trigger", None)

    if not normalized.get("mode"):
        if normalized.get("offset"):
            normalized["mode"] = "relative"
        elif normalized.get("fire_time") or legacy_trigger:
            normalized["mode"] = "absolute"

    if normalized.get("mode") == "absolute":
        if not normalized.get("fire_time") and legacy_trigger:
            normalized["fire_time"] = legacy_trigger
        normalized.setdefault("timezone", None)
        normalized["relation"] = None
        normalized["offset"] = None
    elif normalized.get("mode") == "relative":
        normalized.setdefault("offset", legacy_trigger)
        normalized.setdefault("relation", "START")
    return normalized


def extract_component_datetime(prop: Any) -> Optional[datetime]:
    """Return a datetime object from an iCalendar property value."""
    if not prop:
        return None

    candidate = getattr(prop, "dt", prop)
    if isinstance(candidate, datetime):
        return candidate
    if isinstance(candidate, date):
        return datetime.combine(candidate, datetime.min.time())

    try:
        return datetime.fromisoformat(str(candidate))
    except (TypeError, ValueError):
        return None


def decode_trigger_value(alarm: Any, trigger_prop: Any) -> Any:
    """Safely decode the trigger value to native Python types."""
    if not trigger_prop:
        return None
    try:
        return alarm.decoded("TRIGGER")
    except Exception:
        return trigger_prop


def get_trigger_relation(trigger_prop: Any) -> str:
    """Determine whether a trigger is relative to the event START or END."""
    if trigger_prop and hasattr(trigger_prop, "params"):
        related = trigger_prop.params.get("RELATED")
        if related:
            return str(related).upper()
    return "START"


def coerce_to_datetime(value: Any) -> Optional[datetime]:
    """Convert various trigger representations into a datetime when possible."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())

    dt_value = getattr(value, "dt", None)
    if dt_value is not None and dt_value is not value:
        return coerce_to_datetime(dt_value)

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    try:
        raw = value.to_ical()
        if isinstance(raw, bytes):
            raw = raw.decode()
        if isinstance(raw, str):
            return datetime.fromisoformat(raw)
    except Exception:
        pass
    return None


ISO_DURATION_PATTERN = re.compile(
    r"^(?P<sign>-)?P(?:(?P<days>\d+)D)?"
    r"(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$",
    re.IGNORECASE,
)


def iso8601_to_timedelta(duration: str) -> Optional[timedelta]:
    """Parse a subset of ISO8601 duration strings (PnDTnHnMnS) into timedelta."""
    if not duration:
        return None
    match = ISO_DURATION_PATTERN.fullmatch(duration.strip())
    if not match:
        return None
    sign = -1 if match.group("sign") else 1
    days = int(match.group("days")) if match.group("days") else 0
    hours = int(match.group("hours")) if match.group("hours") else 0
    minutes = int(match.group("minutes")) if match.group("minutes") else 0
    seconds = int(match.group("seconds")) if match.group("seconds") else 0
    delta = timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
    return -delta if sign == -1 else delta


def coerce_to_timedelta(value: Any) -> Optional[timedelta]:
    """Convert trigger representations into timedelta offsets when possible."""
    if isinstance(value, timedelta):
        return value

    duration_candidate = getattr(value, "dt", None)
    if isinstance(duration_candidate, timedelta):
        return duration_candidate

    if isinstance(value, str):
        return iso8601_to_timedelta(value)

    try:
        raw = value.to_ical()
        if isinstance(raw, bytes):
            raw = raw.decode()
        if isinstance(raw, str):
            return iso8601_to_timedelta(raw)
    except Exception:
        pass
    return None


def stringify_trigger(value: Any) -> Optional[str]:
    """Return a safe string representation of a trigger value."""
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode()
    if isinstance(value, str):
        return value
    candidate = getattr(value, "dt", None)
    if candidate is not None and candidate is not value:
        return stringify_trigger(candidate)
    try:
        raw = value.to_ical()
        if isinstance(raw, bytes):
            raw = raw.decode()
        return str(raw)
    except Exception:
        return str(value)


def build_reminder_payload(
    trigger_value: Any,
    related: str,
    event_start: Optional[datetime],
    event_end: Optional[datetime],
    trigger_timezone: Optional[str],
    event_start_timezone: Optional[str],
    event_end_timezone: Optional[str],
) -> Dict[str, Any]:
    """
    Build reminder payload information for the API schema.
    """
    relation = related if related in ("START", "END") else "START"
    reference = event_start if relation != "END" else event_end

    absolute_dt = coerce_to_datetime(trigger_value)
    if absolute_dt:
        timezone = trigger_timezone or timezone_from_datetime(absolute_dt)
        absolute_dt = apply_timezone(absolute_dt, timezone)
        return {
            "mode": "absolute",
            "fire_time": absolute_dt.isoformat(),
            "offset": None,
            "relation": None,
            "timezone": timezone,
        }

    delta = coerce_to_timedelta(trigger_value)
    if delta is not None:
        timezone = event_start_timezone if relation != "END" else event_end_timezone
        aware_reference = apply_timezone(reference, timezone) if reference else None
        fire_time = (aware_reference + delta).isoformat() if aware_reference else None
        return {
            "mode": "relative",
            "fire_time": fire_time,
            "offset": timedelta_to_iso8601(delta),
            "relation": relation,
            "timezone": timezone,
        }

    raw_value = stringify_trigger(trigger_value)
    if raw_value is None:
        raise ValueError("Reminder trigger is missing or unreadable")
    return {
        "mode": "absolute",
        "fire_time": raw_value,
        "offset": None,
        "relation": None,
        "timezone": trigger_timezone,
    }


def timedelta_to_iso8601(delta: timedelta) -> str:
    """Render ``timedelta`` instances as ISO8601 duration strings."""
    total_seconds = int(delta.total_seconds())
    sign = "-" if total_seconds < 0 else ""
    total_seconds = abs(total_seconds)

    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    date_part = f"{days}D" if days else ""

    time_parts = []
    if hours:
        time_parts.append(f"{hours}H")
    if minutes:
        time_parts.append(f"{minutes}M")
    if seconds:
        time_parts.append(f"{seconds}S")

    if not date_part and not time_parts:
        time_parts.append("0S")

    time_part = f"T{''.join(time_parts)}" if time_parts else ""
    return f"{sign}P{date_part}{time_part}"


def reminder_to_ical_trigger(reminder: "Reminder") -> Tuple[Any, Optional[str], Optional[str]]:
    """
    Convert Reminder schema data into values acceptable by the icalendar library.
    """
    if reminder.mode == "relative":
        if not reminder.offset:
            raise ValueError("Relative reminders require offset to be set")
        delta = iso8601_to_timedelta(reminder.offset)
        if delta is None:
            raise ValueError(f"Invalid ISO 8601 duration for reminder offset: {reminder.offset}")
        related = reminder.relation if reminder.relation in ("START", "END") else "START"
        return delta, related, None

    if not reminder.fire_time:
        raise ValueError("Absolute reminders require fire_time to be set")
    trigger_dt = datetime.fromisoformat(reminder.fire_time)
    timezone = reminder.timezone or timezone_from_datetime(trigger_dt)
    trigger_dt = apply_timezone(trigger_dt, timezone)
    if trigger_dt and trigger_dt.tzinfo is not None and timezone is None:
        timezone = timezone_from_datetime(trigger_dt)
    return trigger_dt, None, timezone
