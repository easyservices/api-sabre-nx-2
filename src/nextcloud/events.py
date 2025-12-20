# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Nextcloud CalDAV events module.

This module provides functions to interact with Nextcloud CalDAV events.
It includes functionality to retrieve and search events from a Nextcloud server.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List, Tuple

import icalendar
from dateutil import rrule as du_rrule
from dateutil import parser as du_parser

import caldav
from fastapi import HTTPException
from fastapi.security import HTTPBasicCredentials

from src.common.sec import authenticate_with_nextcloud
from src.models.event import (
    Event,
    RecurrenceInstance,
    FriendlyRecurrence,
)
from src.nextcloud.libs.caldav_helpers import (
    parse_ical_to_event,
    parse_ical_to_events,
    event_to_ical,
    format_datetime,
)
from src.nextcloud.config import get_nextcloud_base_url
from src import logger
from src.common.cache import get_caldav_caches

# Per-user TTL caches to avoid cross-user leakage and unbounded growth
_CALDAV_CACHES = get_caldav_caches()
EVENT_URL_CACHE = _CALDAV_CACHES.event_url
EVENT_CACHE = _CALDAV_CACHES.event_obj
CLIENT_CACHE: Dict[str, caldav.DAVClient] = {}
CALENDAR_CACHE = _CALDAV_CACHES.calendars

def _ensure_list(obj):
    if obj is None:
        return []
    if isinstance(obj, (list, tuple)):
        return list(obj)
    return [obj]

def _client_key(credentials: HTTPBasicCredentials) -> str:
    return f"{credentials.username}:{credentials.password}"

def _user_cache_key(credentials: HTTPBasicCredentials) -> str:
    """Cache key scoped to user (never include password)."""
    return credentials.username or ""

def _event_cache_key(credentials: HTTPBasicCredentials, uid: str) -> str:
    """Cache key combining user and event UID."""
    return f"{_user_cache_key(credentials)}|{uid}"

def _build_client(credentials: HTTPBasicCredentials) -> caldav.DAVClient:
    """Instantiate a CalDAV client for Nextcloud."""
    key = _client_key(credentials)
    if key in CLIENT_CACHE:
        return CLIENT_CACHE[key]
    base_url = get_nextcloud_base_url().rstrip("/")
    client = caldav.DAVClient(
        url=f"{base_url}/remote.php/dav",
        username=credentials.username,
        password=credentials.password,
    )
    CLIENT_CACHE[key] = client
    return client


def _parse_dt(value: str) -> datetime:
    """Parse ISO-like datetime with dateutil for robust handling."""
    if not value:
        raise ValueError("Datetime value is required")
    try:
        return du_parser.isoparse(value)
    except Exception:
        return datetime.fromisoformat(value)


def _duration_from_event(event: Event) -> Optional[timedelta]:
    """Compute duration of an event if end is provided."""
    if not event.start or not event.end:
        return None
    try:
        start_dt = _parse_dt(event.start)
        end_dt = _parse_dt(event.end)
        return end_dt - start_dt
    except Exception:
        return None


def _format_recurrence_id(dt_val: datetime, all_day: bool) -> str:
    """Format RECURRENCE-ID consistently with base event type."""
    if all_day:
        return dt_val.date().isoformat()
    return dt_val.isoformat()


def _normalize_recurrence_id(value: str | datetime, all_day: bool) -> str:
    """Normalize recurrence IDs for consistent matching (drop tz offsets for comparison)."""
    dt_val = value if isinstance(value, datetime) else _parse_dt(str(value))
    if dt_val.tzinfo:
        dt_val = dt_val.replace(tzinfo=None)
    return dt_val.date().isoformat() if all_day else dt_val.isoformat()


def _build_rrule_from_friendly(friendly: FriendlyRecurrence) -> str:
    """Create an RRULE string from friendly recurrence fields."""
    parts = [f"FREQ={friendly.frequency}"]
    if friendly.interval and friendly.interval != 1:
        parts.append(f"INTERVAL={friendly.interval}")
    if friendly.count:
        parts.append(f"COUNT={friendly.count}")
    if friendly.until:
        try:
            until_dt = _parse_dt(friendly.until)
            fmt = "%Y%m%dT%H%M%SZ" if until_dt.tzinfo else "%Y%m%dT%H%M%S"
            parts.append(f"UNTIL={until_dt.strftime(fmt)}")
        except Exception:
            raise ValueError("Invalid until datetime for recurrence")
    if friendly.byweekday:
        parts.append(f"BYDAY={','.join(friendly.byweekday)}")
    if friendly.bymonthday:
        parts.append(f"BYMONTHDAY={','.join(str(day) for day in friendly.bymonthday)}")
    return ";".join(parts)


def _event_to_component(event: Event) -> icalendar.Event:
    """Build an icalendar VEVENT component from an Event model."""
    cal_obj = icalendar.Calendar.from_ical(event_to_ical(event))
    for comp in cal_obj.walk():
        if comp.name == "VEVENT":
            return comp
    raise ValueError("No VEVENT component generated from event")


async def list_calendars(
    credentials: HTTPBasicCredentials,
    user_info: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """
    Return the list of accessible calendars for the authenticated user.

    Each entry contains the calendar display name (when available) and its CalDAV URL.
    Results are cached per user to reduce repeated principal discovery.
    """
    cache_key = _user_cache_key(credentials)
    if cache_key in CALENDAR_CACHE:
        return CALENDAR_CACHE[cache_key]

    user_info = user_info or await authenticate_with_nextcloud(credentials)
    if not isinstance(user_info, dict) or "id" not in user_info:
        raise HTTPException(status_code=500, detail="Invalid user information returned from authentication")

    def _fetch() -> List[Dict[str, str]]:
        client = _build_client(credentials)
        principal = client.principal()
        calendars = principal.calendars()
        result: List[Dict[str, str]] = []
        for cal in calendars:
            try:
                result.append(
                    {
                        "name": getattr(cal, "name", None) or "",
                        "url": str(getattr(cal, "url", "")),
                    }
                )
            except Exception:
                continue
        return result

    try:
        calendars = await asyncio.to_thread(_fetch)
        CALENDAR_CACHE[cache_key] = calendars
        return calendars
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _get_calendar(client: caldav.DAVClient, calendar_name: str) -> caldav.objects.Calendar:
    """Retrieve a calendar by name, preferring the specified one or a personal calendar."""
    principal = client.principal()
    calendars = principal.calendars()
    if not calendars:
        raise HTTPException(status_code=404, detail="No calendars available for this user")

    target_lower = (calendar_name or "").lower()

    # Try exact (case-insensitive) name match
    for cal in calendars:
        try:
            if cal.name and cal.name.lower() == target_lower:
                logger.debug("Using calendar by exact name match: name=%s url=%s", cal.name, cal.url)
                return cal
        except Exception:
            continue

    # Try URL contains the calendar name
    for cal in calendars:
        try:
            if target_lower and target_lower in cal.url.lower():
                logger.debug("Using calendar by URL match: name=%s url=%s", cal.name, cal.url)
                return cal
        except Exception:
            continue

    logger.error("Requested calendar not found", extra={"calendar_name": calendar_name, "available": [getattr(c, 'name', '') for c in calendars]})
    raise HTTPException(status_code=404, detail=f"Calendar '{calendar_name}' not found")


async def _find_event_by_uid(cal: caldav.objects.Calendar, uid: str, privacy: Optional[bool]) -> Optional[Event]:
    """Find an event by UID within a calendar (runs in a thread)."""
    def _search():
        try:
            matches = _ensure_list(cal.event_by_uid(uid))
        except Exception:
            matches = None

        if matches:
            logger.debug("Found %d events via event_by_uid in calendar %s", len(matches), getattr(cal, 'name', ''))
            for ev in matches:
                raw = ev.data
                if not raw:
                    continue
                try:
                    parsed = parse_ical_to_event(raw, ev.url, privacy)
                except Exception as parse_exc:
                    logger.error("Failed to parse event %s: %s", ev.url, parse_exc)
                    continue
                if parsed and parsed.uid == uid:
                    logger.debug("Matched event UID %s at %s", uid, ev.url)
                    return parsed

        events = cal.events()
        logger.debug("Scanning %d events in calendar %s for UID %s", len(events), getattr(cal, 'name', ''), uid)
        for ev in events:
            raw = ev.data
            if not raw:
                continue
            try:
                parsed = parse_ical_to_event(raw, ev.url, privacy)
            except Exception as parse_exc:
                logger.error("Failed to parse event %s: %s", ev.url, parse_exc)
                continue
            if parsed and parsed.uid == uid:
                logger.debug("Matched event UID %s at %s", uid, ev.url)
                return parsed
        logger.debug("No event matched UID %s in calendar %s", uid, getattr(cal, 'name', ''))
        return None

    return await asyncio.to_thread(_search)


async def get_event_by_uid(
    credentials: HTTPBasicCredentials,
    uid: str,
    calendar_name: str = "personal",
    privacy: Optional[bool] = False,
    user_info: Optional[Dict[str, Any]] = None,
) -> Optional[Event]:
    """
    Retrieve a single event by its UID from the specified Nextcloud CalDAV calendar.
    
    This function performs a CalDAV GET request to retrieve a specific event by its UID
    from the specified Nextcloud calendar. It handles the HTTP request, parses the
    iCalendar data, and converts it into an Event object.
    
    Args:
        credentials (HTTPBasicCredentials): HTTP Basic Authentication credentials.
        uid (str): The UID of the event to retrieve.
        calendar_name (Optional[str]): The name of the calendar. Defaults to None (uses "personal").
        
    Returns:
        Optional[Event]: The Event object if found, None otherwise.
        
    Raises:
        HTTPException: For authentication, authorization, server, or parsing errors.
        ValueError: If the uid is empty or None.
    """
    logger.debug(f"get_event_by_uid: retrieving event with UID: {uid} with privacy mode: {privacy}")
        
    user_info = user_info or await authenticate_with_nextcloud(credentials)
    if not isinstance(user_info, dict) or "id" not in user_info:
        raise HTTPException(status_code=500, detail="Invalid user information returned from authentication")
    logger.debug(f"User credentials: {user_info}")
    
    try:
        cache_key = _event_cache_key(credentials, uid)
        cached_url = EVENT_URL_CACHE.get(cache_key)
        if cached_url:
            def _load_by_url():
                client = _build_client(credentials)
                ev = caldav.Event(client=client, url=cached_url)
                ev.load()
                return parse_ical_to_event(ev.data, ev.url, privacy)
            try:
                cached_event = await asyncio.to_thread(_load_by_url)
                if cached_event:
                    return cached_event
            except Exception as exc:
                logger.debug("Cache fetch for UID %s failed: %s", uid, exc)

        # Fallback to in-memory cache when server parsing fails
        if cache_key in EVENT_CACHE:
            return EVENT_CACHE[cache_key]

        client = _build_client(credentials)
        cal = await asyncio.to_thread(_get_calendar, client, calendar_name)
        event = await _find_event_by_uid(cal, uid, privacy)
        if event:
            if event.url:
                EVENT_URL_CACHE[cache_key] = event.url
            EVENT_CACHE[cache_key] = event
        return event
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def get_events_by_time_range(
    credentials: HTTPBasicCredentials,
    start_datetime: str,
    end_datetime: str,
    calendar_name: str = "personal",
    privacy: Optional[bool] = False,
    user_info: Optional[Dict[str, Any]] = None,
) -> List[Event]:
    """
    Retrieve events between a start and end date/time from the specified Nextcloud CalDAV calendar.
    
    This function performs a CalDAV REPORT request with a calendar-query to retrieve events
    that fall within the specified time range. The filtering is done server-side for efficiency.
    
    Args:
        credentials (HTTPBasicCredentials): HTTP Basic Authentication credentials.
        start_datetime (str): Start datetime in ISO format (YYYY-MM-DDTHH:MM:SS).
        end_datetime (str): End datetime in ISO format (YYYY-MM-DDTHH:MM:SS).
        calendar_name (Optional[str]): The name of the calendar. Defaults to None (uses "personal").
        
    Returns:
        List[Event]: A list of Event objects within the specified time range.
        
    Raises:
        HTTPException: For authentication, authorization, server, or parsing errors.
        ValueError: If the datetime parameters are invalid.
    """
    logger.debug(f"get_events_by_time_range: retrieving events between {start_datetime} and {end_datetime} with privacy mode: {privacy}")
        
    user_info = user_info or await authenticate_with_nextcloud(credentials)
    if not isinstance(user_info, dict) or "id" not in user_info:
        raise HTTPException(status_code=500, detail="Invalid user information returned from authentication")
    logger.debug(f"User credentials: {user_info}")
    
    if not start_datetime or not end_datetime:
        raise ValueError("Both start and end datetime must be provided")

    def _search():
        client = _build_client(credentials)
        cal = _get_calendar(client, calendar_name)
        start_dt = datetime.fromisoformat(start_datetime)
        end_dt = datetime.fromisoformat(end_datetime)
        events = []
        fallback_scan = False
        try:
            candidates = cal.date_search(start_dt, end_dt)
        except Exception as search_exc:
            logger.warning(
                "date_search failed, falling back to full scan",
                extra={"calendar": getattr(cal, "name", ""), "error": str(search_exc)},
            )
            candidates = cal.events()
            fallback_scan = True

        for ev in candidates:
            raw = ev.data
            if not raw:
                continue
            try:
                parsed = parse_ical_to_event(raw, ev.url, privacy)
                if not parsed:
                    continue
                # Fallback filter when we scanned all events
                try:
                    ev_start = _parse_dt(parsed.start)
                except Exception:
                    ev_start = None
                if fallback_scan and ev_start:
                    if ev_start < start_dt or ev_start > end_dt:
                        continue
                events.append(parsed)
            except Exception as parse_exc:
                logger.error("Failed to parse event %s: %s", ev.url, parse_exc)
        events.sort(key=lambda ev: ev.start or "")
        return events

    try:
        return await asyncio.to_thread(_search)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def create_event(
    credentials: HTTPBasicCredentials,
    event: Event,
    calendar_name: str = "personal",
    user_info: Optional[Dict[str, Any]] = None,
) -> Event:
    """
    Create a new event in the specified Nextcloud CalDAV calendar.
    
    This function performs a CalDAV PUT request to create a new event in the specified
    Nextcloud calendar. It converts the Event object to iCalendar format and sends it
    to the server.
    
    Args:
        credentials (HTTPBasicCredentials): HTTP Basic Authentication credentials.
        event (Event): The Event object to create.
        calendar_name (Optional[str]): The name of the calendar. Defaults to None (uses "personal").
        
    Returns:
        Event: The created Event object with updated information from the server.
        
    Raises:
        HTTPException: For authentication, authorization, server, or parsing errors.
        ValueError: If the event is invalid or missing required fields.
    """
    logger.debug(f"create_event: received event to create: {event}")
        
    user_info = user_info or await authenticate_with_nextcloud(credentials)
    if not isinstance(user_info, dict) or "id" not in user_info:
        raise HTTPException(status_code=500, detail="Invalid user information returned from authentication")
    logger.debug(f"User credentials: {user_info}")
    
    # Validate the event
    if not event.uid:
        event.uid = Event.generate_uid()
    if not event.summary:
        raise ValueError("Event summary (title) is required")
    if not event.start:
        raise ValueError("Event start time is required")

    ical_data = event_to_ical(event).encode("utf-8")

    def _create():
        client = _build_client(credentials)
        cal = _get_calendar(client, calendar_name)
        new_ev = caldav.Event(client=client, parent=cal, data=ical_data)
        new_ev.save()
        try:
            new_ev.load()
        except Exception:
            pass
        try:
            matches = _ensure_list(cal.event_by_uid(event.uid))
            if matches:
                new_ev = matches[0]
        except Exception:
            logger.debug("event_by_uid lookup after create failed for UID %s", event.uid)
        # caldav library returns URL objects; serialize to string
        event.url = str(new_ev.url) if new_ev.url else None
        cache_key = _event_cache_key(credentials, event.uid)
        if event.url:
            EVENT_URL_CACHE[cache_key] = event.url
        EVENT_CACHE[cache_key] = event
        logger.debug("Created event UID %s in calendar %s at %s", event.uid, getattr(cal, 'name', ''), event.url)
        return event

    try:
        return await asyncio.to_thread(_create)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def update_event(
    credentials: HTTPBasicCredentials,
    event: Event,
    calendar_name: str = "personal",
    user_info: Optional[Dict[str, Any]] = None,
) -> Event:
    """
    Update an existing event in the specified Nextcloud CalDAV calendar.
    
    This function performs a CalDAV PUT request to update an existing event in the specified
    Nextcloud calendar. It converts the Event object to iCalendar format and sends it
    to the server. The event must have a valid UID that exists on the server.
    
    Args:
        credentials (HTTPBasicCredentials): HTTP Basic Authentication credentials.
        event (Event): The Event object with updated information.
        calendar_name (Optional[str]): The name of the calendar. Defaults to None (uses "personal").
        
    Returns:
        Event: The updated Event object with any additional information from the server.
        
    Raises:
        HTTPException: For authentication, authorization, server, or parsing errors.
        ValueError: If the event is invalid, missing required fields, or not found.
    """
    logger.debug(f"update_event: updating event with UID: {event.uid}")
        
    user_info = user_info or await authenticate_with_nextcloud(credentials)
    if not isinstance(user_info, dict) or "id" not in user_info:
        raise HTTPException(status_code=500, detail="Invalid user information returned from authentication")
    logger.debug(f"User credentials: {user_info}")
    
    if not event.uid:
        raise ValueError("Event UID is required for updates")
    if not event.summary:
        raise ValueError("Event summary (title) is required")
    if not event.start:
        raise ValueError("Event start time is required")

    ical_data = event_to_ical(event).encode("utf-8")

    def _update():
        client = _build_client(credentials)
        cal = _get_calendar(client, calendar_name)
        existing = None
        try:
            matches = _ensure_list(cal.event_by_uid(event.uid))
            if matches:
                existing = matches[0]
        except Exception:
            pass

        if existing is None:
            for ev in cal.events():
                raw = ev.data
                if not raw:
                    continue
                try:
                    parsed = parse_ical_to_event(raw, ev.url, False)
                except Exception:
                    continue
                if parsed and parsed.uid == event.uid:
                    existing = ev
                    break

        if not existing:
            raise ValueError(f"Event with UID {event.uid} not found")

        existing.data = ical_data
        existing.save()
        try:
            existing.load()
        except Exception:
            pass
        event.url = str(existing.url) if existing.url else None
        cache_key = _event_cache_key(credentials, event.uid)
        if event.url:
            EVENT_URL_CACHE[cache_key] = event.url
        EVENT_CACHE[cache_key] = event
        logger.debug("Updated event UID %s in calendar %s at %s", event.uid, getattr(cal, 'name', ''), event.url)
        return event

    try:
        return await asyncio.to_thread(_update)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def delete_event(
    credentials: HTTPBasicCredentials,
    uid: str,
    calendar_name: str = "personal",
    user_info: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Delete an event from the specified Nextcloud CalDAV calendar.
    
    This function performs a CalDAV DELETE request to remove an event from the specified
    Nextcloud calendar. It requires the UID of the event to delete.
    
    Args:
        credentials (HTTPBasicCredentials): HTTP Basic Authentication credentials.
        uid (str): The UID of the event to delete.
        calendar_name (Optional[str]): The name of the calendar. Defaults to None (uses "personal").
        
    Returns:
        bool: True if the event was successfully deleted, False if the event was not found.
        
    Raises:
        HTTPException: For authentication, authorization, server, or connection errors.
        ValueError: If the uid is empty or None.
    """
    if not uid:
        raise ValueError("Event UID must be provided for deletion")

    def _delete():
        client = _build_client(credentials)
        cal = _get_calendar(client, calendar_name)
        candidate = None
        try:
            matches = _ensure_list(cal.event_by_uid(uid))
            if matches:
                candidate = matches[0]
        except Exception:
            pass

        if candidate is None:
            for ev in cal.events():
                raw = ev.data
                if not raw:
                    continue
                try:
                    parsed = parse_ical_to_event(raw, ev.url, False)
                except Exception:
                    continue
                if parsed and parsed.uid == uid:
                    candidate = ev
                    break

        if candidate:
            candidate.delete()
            try:
                cache_key = _event_cache_key(credentials, uid)
                EVENT_URL_CACHE.pop(cache_key, None)
                EVENT_CACHE.pop(cache_key, None)
            except Exception:
                pass
            logger.debug("Deleted event UID %s from calendar %s", uid, getattr(cal, 'name', ''))
            return True
        return False

    try:
        return await asyncio.to_thread(_delete)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def _load_recurrence_family(
    credentials: HTTPBasicCredentials,
    uid: str,
    calendar_name: str = "personal",
    privacy: Optional[bool] = False,
    user_info: Optional[Dict[str, Any]] = None,
) -> Tuple[List[Event], Optional[caldav.Event]]:
    """
    Load all VEVENT components sharing a UID (master + exceptions) and return the caldav resource.
    """
    user_info = user_info or await authenticate_with_nextcloud(credentials)
    if not isinstance(user_info, dict) or "id" not in user_info:
        raise HTTPException(status_code=500, detail="Invalid user information returned from authentication")

    def _fetch() -> Tuple[List[Event], Optional[caldav.Event]]:
        cache_key = _event_cache_key(credentials, uid)
        cached_url = EVENT_URL_CACHE.get(cache_key)
        if cached_url:
            try:
                client = _build_client(credentials)
                cal = _get_calendar(client, calendar_name)
                ev = caldav.Event(client=client, url=cached_url, parent=cal)
                ev.load()
                events = parse_ical_to_events(ev.data, str(ev.url), privacy)
                return events, ev
            except Exception:
                pass

        client = _build_client(credentials)
        cal = _get_calendar(client, calendar_name)
        candidate = None
        try:
            matches = _ensure_list(cal.event_by_uid(uid))
            if matches:
                candidate = matches[0]
        except Exception:
            candidate = None

        if candidate is None:
            for ev in cal.events():
                raw = ev.data
                if not raw:
                    continue
                try:
                    parsed = parse_ical_to_event(raw, ev.url, privacy)
                except Exception:
                    continue
                if parsed and parsed.uid == uid:
                    candidate = ev
                    break

        if candidate is None:
            return [], None

        candidate.load()
        events = parse_ical_to_events(candidate.data, str(candidate.url), privacy)
        if events and candidate.url:
            EVENT_URL_CACHE[_event_cache_key(credentials, uid)] = str(candidate.url)
        return events, candidate

    try:
        return await asyncio.to_thread(_fetch)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def expand_recurrence_instances(
    credentials: HTTPBasicCredentials,
    uid: str,
    start_datetime: str,
    end_datetime: str,
    calendar_name: str = "personal",
    privacy: Optional[bool] = False,
    user_info: Optional[Dict[str, Any]] = None,
) -> List[RecurrenceInstance]:
    """Expand a recurring event into concrete instances between the given window."""
    if not start_datetime or not end_datetime:
        raise ValueError("start_datetime and end_datetime are required")

    window_start = _parse_dt(start_datetime)
    window_end = _parse_dt(end_datetime)
    events, _resource = await _load_recurrence_family(credentials, uid, calendar_name, privacy, user_info)
    if not events:
        raise HTTPException(status_code=404, detail=f"Event with UID {uid} not found")

    base_event = next((ev for ev in events if not ev.recurrence_id), None)
    if base_event is None:
        base_event = events[0]

    if not base_event.recurrence:
        raise HTTPException(status_code=400, detail="Event is not recurring")

    base_start = _parse_dt(base_event.start)
    # Keep original occurrences visible even if client window starts slightly after the first instance
    if base_start < window_start:
        window_start = base_start
    try:
        rule = du_rrule.rrulestr(base_event.recurrence, dtstart=base_start)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid recurrence rule: {exc}") from exc

    duration = _duration_from_event(base_event)
    overrides = {}
    for ev in events:
        if not ev.recurrence_id:
            continue
        try:
            norm_id = _normalize_recurrence_id(ev.recurrence_id, ev.all_day)
        except Exception:
            norm_id = ev.recurrence_id
        overrides[norm_id] = ev
    exdates_raw = base_event.exdate or []

    def _matches_exdate(dt_val: datetime) -> bool:
        for raw in exdates_raw:
            try:
                ex_dt = _parse_dt(raw)
            except Exception:
                continue
            if base_event.all_day:
                if dt_val.date() == ex_dt.date():
                    return True
            else:
                if dt_val.replace(tzinfo=None) == ex_dt.replace(tzinfo=None):
                    return True
        return False

    instances: List[RecurrenceInstance] = []
    for occ in rule.between(window_start, window_end, inc=True):
        if _matches_exdate(occ):
            continue
        rec_id = _normalize_recurrence_id(occ, base_event.all_day)
        override = overrides.get(rec_id)
        current_all_day = override.all_day if override and override.all_day is not None else base_event.all_day

        if override:
            start_val = override.start or rec_id
            end_val = override.end
            if not end_val and duration:
                try:
                    end_val = (_parse_dt(start_val) + duration).isoformat()
                except Exception:
                    end_val = override.end or base_event.end
        else:
            start_val = occ.isoformat()
            if duration:
                end_val = (occ + duration).isoformat()
            else:
                end_val = base_event.end

        instances.append(
            RecurrenceInstance(
                recurrence_id=rec_id,
                start=start_val,
                end=end_val,
                all_day=bool(current_all_day),
                source_uid=uid,
                url=override.url if override and override.url else base_event.url,
                overrides_applied=bool(override),
            )
        )

    instances.sort(key=lambda inst: inst.start or "")
    return instances


def preview_recurrence(
    start: str,
    end: Optional[str],
    all_day: bool,
    friendly: Optional[FriendlyRecurrence],
    rrule: Optional[str],
    max_occurrences: int = 20,
) -> Dict[str, Any]:
    """
    Build a recurrence preview using either a raw RRULE or friendly payload.
    """
    start_dt = _parse_dt(start)
    duration = None
    if end:
        try:
            duration = _parse_dt(end) - start_dt
        except Exception:
            duration = None

    if friendly:
        rrule_str = _build_rrule_from_friendly(friendly)
        exclusions = friendly.exclusions or []
    else:
        rrule_str = rrule or ""
        exclusions = []

    if not rrule_str:
        raise ValueError("No recurrence rule provided")

    rset = du_rrule.rruleset()
    rset.rrule(du_rrule.rrulestr(rrule_str, dtstart=start_dt))
    for ex in exclusions:
        try:
            rset.exdate(_parse_dt(ex))
        except Exception:
            continue

    occurrences: List[RecurrenceInstance] = []
    for occ in rset:
        rec_id = _format_recurrence_id(occ, all_day)
        end_val = None
        if duration:
            end_val = (occ + duration).isoformat()
        occurrences.append(
            RecurrenceInstance(
                recurrence_id=rec_id,
                start=occ.date().isoformat() if all_day else occ.isoformat(),
                end=end_val.date().isoformat() if end_val and all_day else end_val,
                all_day=all_day,
                source_uid="preview",
                overrides_applied=False,
            )
        )
        if len(occurrences) >= max_occurrences:
            break

    return {
        "rrule": rrule_str,
        "occurrences": occurrences,
        "excluded": exclusions,
    }


def build_recurrence_rule(friendly: FriendlyRecurrence) -> Dict[str, Any]:
    """Generate an RRULE string and lightweight summary from friendly fields."""
    rrule_str = _build_rrule_from_friendly(friendly)
    summary_parts = [friendly.frequency.capitalize()]
    if friendly.interval and friendly.interval > 1:
        summary_parts.append(f"every {friendly.interval}")
    if friendly.byweekday:
        summary_parts.append(f"on {', '.join(friendly.byweekday)}")
    if friendly.bymonthday:
        summary_parts.append(f"on days {', '.join(str(x) for x in friendly.bymonthday)}")
    if friendly.count:
        summary_parts.append(f"count={friendly.count}")
    if friendly.until:
        summary_parts.append(f"until {friendly.until}")

    return {"rrule": rrule_str, "summary": " ".join(summary_parts)}


async def upsert_recurrence_exception(
    credentials: HTTPBasicCredentials,
    uid: str,
    recurrence_id: str,
    overrides: Dict[str, Any],
    calendar_name: str = "personal",
    user_info: Optional[Dict[str, Any]] = None,
    privacy: Optional[bool] = False,
) -> Event:
    """
    Upsert a specific recurrence exception by adding/replacing a RECURRENCE-ID component.
    """
    events, resource = await _load_recurrence_family(credentials, uid, calendar_name, privacy, user_info)
    if not events or resource is None:
        raise HTTPException(status_code=404, detail=f"Event with UID {uid} not found")
    base_event = next((ev for ev in events if not ev.recurrence_id), None) or events[0]
    if not base_event.recurrence:
        raise HTTPException(status_code=400, detail="Event is not recurring")

    duration = _duration_from_event(base_event)
    start_val = overrides.get("start") or recurrence_id or base_event.start
    end_val = overrides.get("end") or base_event.end
    if duration and overrides.get("end") is None and start_val:
        try:
            end_val = (_parse_dt(start_val) + duration).isoformat()
        except Exception:
            end_val = base_event.end

    merged = Event(
        uid=uid,
        summary=overrides.get("summary") or base_event.summary,
        description=overrides.get("description") if "description" in overrides else base_event.description,
        location=overrides.get("location") if "location" in overrides else base_event.location,
        status=overrides.get("status") if "status" in overrides else base_event.status,
        start=start_val,
        end=end_val,
        all_day=overrides.get("all_day") if "all_day" in overrides else base_event.all_day,
        recurrence=base_event.recurrence,
        recurrence_id=recurrence_id,
        categories=overrides.get("categories") if "categories" in overrides else base_event.categories,
        attendees=overrides.get("attendees") if "attendees" in overrides else base_event.attendees,
        reminders=overrides.get("reminders") if "reminders" in overrides else base_event.reminders,
        organizer=base_event.organizer,
        exdate=base_event.exdate,
    )

    def _apply():
        resource.load()
        cal_obj = icalendar.Calendar.from_ical(resource.data)
        # Remove existing exception with same RECURRENCE-ID if present
        target_id = _parse_dt(recurrence_id)
        target_key = _format_recurrence_id(target_id, merged.all_day)
        cal_obj.subcomponents = [
            comp
            for comp in cal_obj.subcomponents
            if not (
                getattr(comp, "name", "").upper() == "VEVENT"
                and comp.get("RECURRENCE-ID")
                and _format_recurrence_id(_parse_dt(format_datetime(comp.get("RECURRENCE-ID"))), merged.all_day) == target_key
            )
        ]
        new_component = _event_to_component(merged)
        cal_obj.add_component(new_component)
        resource.data = cal_obj.to_ical()
        resource.save()
        # Return the merged occurrence parsed back
        url_hint = str(resource.url) if getattr(resource, "url", None) else ""
        updated = parse_ical_to_events(resource.data, url_hint, privacy)
        for ev in updated:
            if ev.recurrence_id == merged.recurrence_id:
                return ev
        return merged

    try:
        return await asyncio.to_thread(_apply)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def skip_recurrence_instances(
    credentials: HTTPBasicCredentials,
    uid: str,
    recurrence_ids: List[str],
    calendar_name: str = "personal",
    user_info: Optional[Dict[str, Any]] = None,
    privacy: Optional[bool] = False,
) -> Event:
    """Add EXDATE entries to skip specific recurrence instances."""
    events, resource = await _load_recurrence_family(credentials, uid, calendar_name, privacy, user_info)
    if not events or resource is None:
        raise HTTPException(status_code=404, detail=f"Event with UID {uid} not found")
    base_event = next((ev for ev in events if not ev.recurrence_id), None) or events[0]
    if not base_event.recurrence:
        raise HTTPException(status_code=400, detail="Event is not recurring")

    def _apply_skip():
        resource.load()
        cal_obj = icalendar.Calendar.from_ical(resource.data)
        master = None
        for comp in cal_obj.walk():
            if getattr(comp, "name", "").upper() == "VEVENT" and not comp.get("RECURRENCE-ID"):
                master = comp
                break
        if master is None:
            raise ValueError("Master event component not found for recurrence")

        for rec_id in recurrence_ids:
            try:
                dt_val = _parse_dt(rec_id)
            except Exception:
                continue
            master.add("exdate", dt_val.date() if base_event.all_day else dt_val)

        resource.data = cal_obj.to_ical()
        resource.save()
        url_hint = str(resource.url) if getattr(resource, "url", None) else ""
        updated = parse_ical_to_events(resource.data, url_hint, privacy)
        for ev in updated:
            if not ev.recurrence_id:
                return ev
        return base_event

    try:
        return await asyncio.to_thread(_apply_skip)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
