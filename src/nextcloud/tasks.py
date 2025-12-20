# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Nextcloud CalDAV tasks (VTODO) module.

Provides read/write helpers for tasks to keep parity with the events implementation.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import icalendar
from dateutil import rrule as du_rrule
from dateutil import parser as du_parser

import caldav
from fastapi import HTTPException
from fastapi.security import HTTPBasicCredentials

from src import logger
from src.common.cache import get_caldav_caches
from src.common.sec import authenticate_with_nextcloud
from src.models.task import Task
from src.nextcloud.config import get_nextcloud_base_url
from src.nextcloud.libs.caldav_todo_helpers import parse_ical_to_task, task_to_ical, parse_ical_to_tasks
from src.models.event import RecurrenceInstance, FriendlyRecurrence
from src.nextcloud.events import preview_recurrence, build_recurrence_rule, _parse_dt as _parse_event_dt, _normalize_recurrence_id as _normalize_event_recurrence_id

# Per-user TTL caches to avoid cross-user leakage and unbounded growth
_CALDAV_CACHES = get_caldav_caches()
TODO_URL_CACHE = _CALDAV_CACHES.todo_url
TODO_CACHE = _CALDAV_CACHES.todo_obj
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


def _task_cache_key(credentials: HTTPBasicCredentials, uid: str) -> str:
    """Cache key combining user and task UID."""
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
    return _parse_event_dt(value)


def _normalize_recurrence_id(value: str | datetime, all_day: bool) -> str:
    return _normalize_event_recurrence_id(value, all_day)


def _duration_from_task(task: Task) -> Optional[timedelta]:
    """Compute duration from start/due when available."""
    if not task.start or not task.due:
        return None
    try:
        return _parse_dt(task.due) - _parse_dt(task.start)
    except Exception:
        return None


def _task_component(task: Task) -> icalendar.Todo:
    cal_obj = icalendar.Calendar.from_ical(task_to_ical(task))
    for comp in cal_obj.walk():
        if comp.name == "VTODO":
            return comp
    raise ValueError("No VTODO component generated from task")


async def list_calendars(
    credentials: HTTPBasicCredentials,
    user_info: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, str]]:
    """
    Return the list of accessible calendars for the authenticated user.

    Reuses the same cache as events since the CalDAV collection list is shared.
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

    for cal in calendars:
        try:
            if cal.name and cal.name.lower() == target_lower:
                logger.debug("Using calendar by exact name match: name=%s url=%s", cal.name, cal.url)
                return cal
        except Exception:
            continue

    for cal in calendars:
        try:
            if target_lower and target_lower in cal.url.lower():
                logger.debug("Using calendar by URL match: name=%s url=%s", cal.name, cal.url)
                return cal
        except Exception:
            continue

    logger.error("Requested calendar not found", extra={"calendar_name": calendar_name, "available": [getattr(c, 'name', '') for c in calendars]})
    raise HTTPException(status_code=404, detail=f"Calendar '{calendar_name}' not found")


async def _find_task_by_uid(cal: caldav.objects.Calendar, uid: str, privacy: Optional[bool]) -> Optional[Task]:
    """Find a task by UID within a calendar (runs in a thread)."""

    def _search():
        try:
            matches = _ensure_list(cal.todo_by_uid(uid))
        except Exception:
            matches = None

        if matches:
            logger.debug("Found %d tasks via todo_by_uid in calendar %s", len(matches), getattr(cal, "name", ""))
            for td in matches:
                raw = td.data
                if not raw:
                    continue
                try:
                    parsed = parse_ical_to_task(raw, td.url, privacy)
                except Exception as parse_exc:
                    logger.error("Failed to parse task %s: %s", td.url, parse_exc)
                    continue
                if parsed and parsed.uid == uid:
                    logger.debug("Matched task UID %s at %s", uid, td.url)
                    return parsed

        todos = cal.todos()
        logger.debug("Scanning %d tasks in calendar %s for UID %s", len(todos), getattr(cal, "name", ""), uid)
        for td in todos:
            raw = td.data
            if not raw:
                continue
            try:
                parsed = parse_ical_to_task(raw, td.url, privacy)
            except Exception as parse_exc:
                logger.error("Failed to parse task %s: %s", td.url, parse_exc)
                continue
            if parsed and parsed.uid == uid:
                logger.debug("Matched task UID %s at %s", uid, td.url)
                return parsed
        logger.debug("No task matched UID %s in calendar %s", uid, getattr(cal, "name", ""))
        return None

    return await asyncio.to_thread(_search)


async def get_task_by_uid(
    credentials: HTTPBasicCredentials,
    uid: str,
    calendar_name: str = "personal",
    privacy: Optional[bool] = False,
    user_info: Optional[Dict[str, Any]] = None,
) -> Optional[Task]:
    """Retrieve a single task by its UID from the specified Nextcloud CalDAV calendar."""
    logger.debug("get_task_by_uid: retrieving task with UID %s with privacy mode: %s", uid, privacy)

    user_info = user_info or await authenticate_with_nextcloud(credentials)
    if not isinstance(user_info, dict) or "id" not in user_info:
        raise HTTPException(status_code=500, detail="Invalid user information returned from authentication")
    logger.debug("User credentials: %s", user_info)

    try:
        cache_key = _task_cache_key(credentials, uid)
        cached_url = TODO_URL_CACHE.get(cache_key)
        if cached_url:
            def _load_by_url():
                client = _build_client(credentials)
                td = caldav.Todo(client=client, url=cached_url)
                td.load()
                return parse_ical_to_task(td.data, td.url, privacy)
            try:
                cached_task = await asyncio.to_thread(_load_by_url)
                if cached_task:
                    return cached_task
            except Exception as exc:
                logger.debug("Cache fetch for UID %s failed: %s", uid, exc)

        if cache_key in TODO_CACHE:
            return TODO_CACHE[cache_key]

        client = _build_client(credentials)
        cal = await asyncio.to_thread(_get_calendar, client, calendar_name)
        task = await _find_task_by_uid(cal, uid, privacy)
        if task:
            if task.url:
                TODO_URL_CACHE[cache_key] = task.url
            TODO_CACHE[cache_key] = task
        return task
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def get_tasks_by_time_range(
    credentials: HTTPBasicCredentials,
    start_datetime: str,
    end_datetime: str,
    calendar_name: str = "personal",
    privacy: Optional[bool] = False,
    user_info: Optional[Dict[str, Any]] = None,
) -> List[Task]:
    """Retrieve tasks between a start and end date/time from the specified calendar."""
    logger.debug("get_tasks_by_time_range: retrieving tasks between %s and %s with privacy mode: %s", start_datetime, end_datetime, privacy)

    user_info = user_info or await authenticate_with_nextcloud(credentials)
    if not isinstance(user_info, dict) or "id" not in user_info:
        raise HTTPException(status_code=500, detail="Invalid user information returned from authentication")
    logger.debug("User credentials: %s", user_info)

    if not start_datetime or not end_datetime:
        raise ValueError("Both start and end datetime must be provided")

    def _search():
        client = _build_client(credentials)
        cal = _get_calendar(client, calendar_name)
        start_dt = datetime.fromisoformat(start_datetime)
        end_dt = datetime.fromisoformat(end_datetime)
        tasks: List[Task] = []
        fallback_scan = False

        def _consume(candidates, use_fallback: bool):
            collected: List[Task] = []
            try:
                for td in candidates:
                    raw = td.data
                    if not raw:
                        continue
                    try:
                        parsed = parse_ical_to_task(raw, td.url, privacy)
                        if not parsed:
                            continue
                        if use_fallback:
                            try:
                                start_val = _parse_dt(parsed.start) if parsed.start else None
                                due_val = _parse_dt(parsed.due) if parsed.due else None
                                pivot = start_val or due_val
                            except Exception:
                                pivot = None
                            if pivot and (pivot < start_dt or pivot > end_dt):
                                continue
                        collected.append(parsed)
                    except Exception as parse_exc:
                        logger.error("Failed to parse task %s: %s", td.url, parse_exc)
                return collected
            except Exception as iter_exc:
                logger.warning(
                    "task date_search iteration failed, will fallback",
                    extra={"calendar": getattr(cal, "name", ""), "error": str(iter_exc)},
                )
                return None
            return collected

        try:
            candidates = cal.date_search(start_dt, end_dt, compfilter="VTODO")
            tasks = _consume(candidates, False)
            if tasks is None:
                raise Exception("date_search iteration failed")
        except Exception as search_exc:
            logger.warning(
                "task date_search failed, falling back to full scan",
                extra={"calendar": getattr(cal, "name", ""), "error": str(search_exc)},
            )
            fallback_scan = True
            try:
                tasks = _consume(cal.todos(), True)
            except Exception as fallback_exc:
                logger.warning(
                    "task full scan failed",
                    extra={"calendar": getattr(cal, "name", ""), "error": str(fallback_exc)},
                )
                tasks = []

        tasks = tasks or []
        tasks.sort(key=lambda task: task.due or task.start or "")
        return tasks

    try:
        return await asyncio.to_thread(_search)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def create_task(
    credentials: HTTPBasicCredentials,
    task: Task,
    calendar_name: str = "personal",
    user_info: Optional[Dict[str, Any]] = None,
) -> Task:
    """Create a new task in the specified Nextcloud CalDAV calendar."""
    logger.debug("create_task: received task to create: %s", task)

    user_info = user_info or await authenticate_with_nextcloud(credentials)
    if not isinstance(user_info, dict) or "id" not in user_info:
        raise HTTPException(status_code=500, detail="Invalid user information returned from authentication")
    logger.debug("User credentials: %s", user_info)

    if not task.uid:
        task.uid = Task.generate_uid()
    if not task.summary:
        raise ValueError("Task summary (title) is required")

    ical_data = task_to_ical(task).encode("utf-8")

    def _create():
        client = _build_client(credentials)
        cal = _get_calendar(client, calendar_name)
        new_td = caldav.Todo(client=client, parent=cal, data=ical_data)
        new_td.save()
        try:
            new_td.load()
        except Exception:
            pass
        try:
            matches = _ensure_list(cal.todo_by_uid(task.uid))
            if matches:
                new_td = matches[0]
        except Exception:
            logger.debug("todo_by_uid lookup after create failed for UID %s", task.uid)
        task.url = str(new_td.url) if new_td.url else None
        cache_key = _task_cache_key(credentials, task.uid)
        if task.url:
            TODO_URL_CACHE[cache_key] = task.url
        TODO_CACHE[cache_key] = task
        logger.debug("Created task UID %s in calendar %s at %s", task.uid, getattr(cal, "name", ""), task.url)
        return task

    try:
        return await asyncio.to_thread(_create)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def update_task(
    credentials: HTTPBasicCredentials,
    task: Task,
    calendar_name: str = "personal",
    user_info: Optional[Dict[str, Any]] = None,
) -> Task:
    """Update an existing task in the specified Nextcloud CalDAV calendar."""
    logger.debug("update_task: updating task with UID: %s", task.uid)

    user_info = user_info or await authenticate_with_nextcloud(credentials)
    if not isinstance(user_info, dict) or "id" not in user_info:
        raise HTTPException(status_code=500, detail="Invalid user information returned from authentication")
    logger.debug("User credentials: %s", user_info)

    if not task.uid:
        raise ValueError("Task UID is required for updates")
    if not task.summary:
        raise ValueError("Task summary (title) is required")

    ical_data = task_to_ical(task).encode("utf-8")

    def _update():
        client = _build_client(credentials)
        cal = _get_calendar(client, calendar_name)
        existing = None
        try:
            matches = _ensure_list(cal.todo_by_uid(task.uid))
            if matches:
                existing = matches[0]
        except Exception:
            pass

        if existing is None:
            for td in cal.todos():
                raw = td.data
                if not raw:
                    continue
                try:
                    parsed = parse_ical_to_task(raw, td.url, False)
                except Exception:
                    continue
                if parsed and parsed.uid == task.uid:
                    existing = td
                    break

        if not existing:
            raise ValueError(f"Task with UID {task.uid} not found")

        existing.data = ical_data
        existing.save()
        try:
            existing.load()
        except Exception:
            pass
        task.url = str(existing.url) if existing.url else None
        cache_key = _task_cache_key(credentials, task.uid)
        if task.url:
            TODO_URL_CACHE[cache_key] = task.url
        TODO_CACHE[cache_key] = task
        logger.debug("Updated task UID %s in calendar %s at %s", task.uid, getattr(cal, "name", ""), task.url)
        return task

    try:
        return await asyncio.to_thread(_update)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def delete_task(
    credentials: HTTPBasicCredentials,
    uid: str,
    calendar_name: str = "personal",
    user_info: Optional[Dict[str, Any]] = None,
) -> bool:
    """Delete a task from the specified Nextcloud CalDAV calendar."""
    if not uid:
        raise ValueError("Task UID must be provided for deletion")

    def _delete():
        client = _build_client(credentials)
        cal = _get_calendar(client, calendar_name)
        cache_key = _task_cache_key(credentials, uid)
        cached_url = TODO_URL_CACHE.get(cache_key)
        if cached_url:
            try:
                td = caldav.Todo(client=client, url=cached_url, parent=cal)
                td.delete()
                TODO_URL_CACHE.pop(cache_key, None)
                TODO_CACHE.pop(cache_key, None)
                logger.debug("Deleted task UID %s via cached URL %s", uid, cached_url)
                return True
            except Exception:
                pass
        candidate = None
        try:
            matches = _ensure_list(cal.todo_by_uid(uid))
            if matches:
                candidate = matches[0]
        except Exception:
            pass

        if candidate is None:
            for td in cal.todos():
                raw = td.data
                if not raw:
                    continue
                try:
                    parsed = parse_ical_to_task(raw, td.url, False)
                except Exception:
                    continue
                if parsed and parsed.uid == uid:
                    candidate = td
                    break

        if candidate:
            candidate.delete()
            try:
                cache_key = _task_cache_key(credentials, uid)
                TODO_URL_CACHE.pop(cache_key, None)
                TODO_CACHE.pop(cache_key, None)
            except Exception:
                pass
            logger.debug("Deleted task UID %s from calendar %s", uid, getattr(cal, "name", ""))
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
) -> Tuple[List[Task], Optional[caldav.Todo]]:
    """
    Load all VTODO components sharing a UID (master + exceptions) and return the caldav resource.
    """
    user_info = user_info or await authenticate_with_nextcloud(credentials)
    if not isinstance(user_info, dict) or "id" not in user_info:
        raise HTTPException(status_code=500, detail="Invalid user information returned from authentication")

    def _fetch() -> Tuple[List[Task], Optional[caldav.Todo]]:
        cache_key = _task_cache_key(credentials, uid)
        cached_url = TODO_URL_CACHE.get(cache_key)
        if cached_url:
            try:
                client = _build_client(credentials)
                cal = _get_calendar(client, calendar_name)
                td = caldav.Todo(client=client, url=cached_url, parent=cal)
                td.load()
                tasks = parse_ical_to_tasks(td.data, str(td.url), privacy)
                return tasks, td
            except Exception:
                pass

        client = _build_client(credentials)
        cal = _get_calendar(client, calendar_name)
        candidate = None
        try:
            matches = _ensure_list(cal.todo_by_uid(uid))
            if matches:
                candidate = matches[0]
        except Exception:
            candidate = None

        if candidate is None:
            for td in cal.todos():
                raw = td.data
                if not raw:
                    continue
                try:
                    parsed = parse_ical_to_task(raw, td.url, privacy)
                except Exception:
                    continue
                if parsed and parsed.uid == uid:
                    candidate = td
                    break

        if candidate is None:
            return [], None

        candidate.load()
        tasks = parse_ical_to_tasks(candidate.data, str(candidate.url), privacy)
        if tasks and candidate.url:
            TODO_URL_CACHE[_task_cache_key(credentials, uid)] = str(candidate.url)
        return tasks, candidate

    try:
        return await asyncio.to_thread(_fetch)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def expand_task_recurrence_instances(
    credentials: HTTPBasicCredentials,
    uid: str,
    start_datetime: str,
    end_datetime: str,
    calendar_name: str = "personal",
    privacy: Optional[bool] = False,
    user_info: Optional[Dict[str, Any]] = None,
) -> List[RecurrenceInstance]:
    """Expand a recurring task into concrete instances between the given window."""
    if not start_datetime or not end_datetime:
        raise ValueError("start_datetime and end_datetime are required")

    window_start = _parse_dt(start_datetime)
    window_end = _parse_dt(end_datetime)
    tasks, _resource = await _load_recurrence_family(credentials, uid, calendar_name, privacy, user_info)
    if not tasks:
        raise HTTPException(status_code=404, detail=f"Task with UID {uid} not found")

    base_task = next((td for td in tasks if not td.recurrence_id), None) or tasks[0]
    if not base_task.recurrence:
        raise HTTPException(status_code=400, detail="Task is not recurring")

    base_start = _parse_dt(base_task.start or base_task.due)
    if base_start < window_start:
        window_start = base_start
    try:
        rule = du_rrule.rrulestr(base_task.recurrence, dtstart=base_start)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid recurrence rule: {exc}") from exc

    duration = _duration_from_task(base_task)
    overrides: Dict[str, Task] = {}
    for td in tasks:
        if not td.recurrence_id:
            continue
        try:
            norm_id = _normalize_recurrence_id(td.recurrence_id, td.all_day)
        except Exception:
            norm_id = td.recurrence_id
        overrides[norm_id] = td

    exdates_raw = base_task.exdate or []

    def _matches_exdate(dt_val: datetime) -> bool:
        for raw in exdates_raw:
            try:
                ex_dt = _parse_dt(raw)
            except Exception:
                continue
            if base_task.all_day:
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
        rec_id = _normalize_recurrence_id(occ, base_task.all_day)
        override = overrides.get(rec_id)
        current_all_day = override.all_day if override and override.all_day is not None else base_task.all_day

        if override:
            start_val = override.start or override.due or rec_id
            end_val = override.due
            if not end_val and duration:
                try:
                    end_val = (_parse_dt(start_val) + duration).isoformat()
                except Exception:
                    end_val = override.due or base_task.due
        else:
            start_val = occ.isoformat()
            if duration:
                end_val = (occ + duration).isoformat()
            else:
                end_val = base_task.due

        instances.append(
            RecurrenceInstance(
                recurrence_id=rec_id,
                start=start_val,
                end=end_val,
                all_day=bool(current_all_day),
                source_uid=uid,
                url=override.url if override and override.url else base_task.url,
                overrides_applied=bool(override),
            )
        )

    instances.sort(key=lambda inst: inst.start or "")
    return instances


async def upsert_task_recurrence_exception(
    credentials: HTTPBasicCredentials,
    uid: str,
    recurrence_id: str,
    overrides: Dict[str, Any],
    calendar_name: str = "personal",
    user_info: Optional[Dict[str, Any]] = None,
    privacy: Optional[bool] = False,
) -> Task:
    """Upsert a specific recurrence exception by adding/replacing a RECURRENCE-ID component for a task."""
    tasks, resource = await _load_recurrence_family(credentials, uid, calendar_name, privacy, user_info)
    if not tasks or resource is None:
        raise HTTPException(status_code=404, detail=f"Task with UID {uid} not found")
    base_task = next((td for td in tasks if not td.recurrence_id), None) or tasks[0]
    if not base_task.recurrence:
        raise HTTPException(status_code=400, detail="Task is not recurring")

    duration = _duration_from_task(base_task)
    start_val = overrides.get("start") or overrides.get("due") or recurrence_id or base_task.start or base_task.due
    due_val = overrides.get("due") or base_task.due
    if duration and overrides.get("due") is None and start_val:
        try:
            due_val = (_parse_dt(start_val) + duration).isoformat()
        except Exception:
            due_val = base_task.due

    merged = Task(
        uid=uid,
        summary=overrides.get("summary") or base_task.summary,
        description=overrides.get("description") if "description" in overrides else base_task.description,
        status=overrides.get("status") if "status" in overrides else base_task.status,
        start=start_val if base_task.start else None,
        due=due_val,
        completed=base_task.completed,
        all_day=overrides.get("all_day") if "all_day" in overrides else base_task.all_day,
        recurrence=base_task.recurrence,
        recurrence_id=recurrence_id,
        categories=overrides.get("categories") if "categories" in overrides else base_task.categories,
        attendees=overrides.get("attendees") if "attendees" in overrides else base_task.attendees,
        reminders=overrides.get("reminders") if "reminders" in overrides else base_task.reminders,
        organizer=base_task.organizer,
        percent_complete=overrides.get("percent_complete") if "percent_complete" in overrides else base_task.percent_complete,
        priority=overrides.get("priority") if "priority" in overrides else base_task.priority,
        exdate=base_task.exdate,
        url=base_task.url,
    )

    def _apply():
        resource.load()
        cal_obj = icalendar.Calendar.from_ical(resource.data)
        target_id = _parse_dt(recurrence_id)
        target_key = _normalize_recurrence_id(target_id, merged.all_day or False)
        cal_obj.subcomponents = [
            comp
            for comp in cal_obj.subcomponents
            if not (
                getattr(comp, "name", "").upper() == "VTODO"
                and comp.get("RECURRENCE-ID")
                and _normalize_recurrence_id(format_datetime(comp.get("RECURRENCE-ID")), merged.all_day or False) == target_key
            )
        ]
        new_component = _task_component(merged)
        cal_obj.add_component(new_component)
        resource.data = cal_obj.to_ical()
        resource.save()
        url_hint = str(resource.url) if getattr(resource, "url", None) else ""
        updated = parse_ical_to_tasks(resource.data, url_hint, privacy)
        for td in updated:
            if td.recurrence_id == merged.recurrence_id:
                return td
        return merged

    try:
        return await asyncio.to_thread(_apply)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


async def skip_task_recurrence_instances(
    credentials: HTTPBasicCredentials,
    uid: str,
    recurrence_ids: List[str],
    calendar_name: str = "personal",
    user_info: Optional[Dict[str, Any]] = None,
    privacy: Optional[bool] = False,
) -> Task:
    """Add EXDATE entries to skip specific recurrence instances for tasks."""
    tasks, resource = await _load_recurrence_family(credentials, uid, calendar_name, privacy, user_info)
    if not tasks or resource is None:
        raise HTTPException(status_code=404, detail=f"Task with UID {uid} not found")
    base_task = next((td for td in tasks if not td.recurrence_id), None) or tasks[0]
    if not base_task.recurrence:
        raise HTTPException(status_code=400, detail="Task is not recurring")

    def _apply_skip():
        resource.load()
        cal_obj = icalendar.Calendar.from_ical(resource.data)
        master = None
        for comp in cal_obj.walk():
            if getattr(comp, "name", "").upper() == "VTODO" and not comp.get("RECURRENCE-ID"):
                master = comp
                break
        if master is None:
            raise ValueError("Master task component not found for recurrence")

        for rec_id in recurrence_ids:
            try:
                dt_val = _parse_dt(rec_id)
            except Exception:
                continue
            master.add("exdate", dt_val.date() if base_task.all_day else dt_val)

        resource.data = cal_obj.to_ical()
        resource.save()
        url_hint = str(resource.url) if getattr(resource, "url", None) else ""
        updated = parse_ical_to_tasks(resource.data, url_hint, privacy)
        for td in updated:
            if not td.recurrence_id:
                return td
        return base_task

    try:
        return await asyncio.to_thread(_apply_skip)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def preview_task_recurrence(
    start: str,
    end: Optional[str],
    all_day: bool,
    friendly: Optional[FriendlyRecurrence],
    rrule: Optional[str],
    max_occurrences: int = 20,
):
    """Wrapper to preview recurrence using shared event helper for tasks."""
    return preview_recurrence(
        start=start,
        end=end,
        all_day=all_day,
        friendly=friendly,
        rrule=rrule,
        max_occurrences=max_occurrences,
    )


def build_task_recurrence_rule(friendly: FriendlyRecurrence):
    """Wrapper to build RRULE for tasks using shared helper."""
    return build_recurrence_rule(friendly)
