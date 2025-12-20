# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Helper functions for CalDAV VTODO operations.

These mirror the VEVENT helpers but target tasks (VTODO) to keep /tasks symmetric
with the existing /events API surface.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime

import icalendar

from src.models.task import Task
from src.nextcloud.libs import PRIVACY_MODE_TXT
from src.nextcloud.libs.caldav_helpers import (
    format_datetime,
    parse_attendees,
    parse_reminders,
)
from src.nextcloud.libs.carddav_helpers import validate_and_correct_url

# Some icalendar versions expose ValidationError at the top level; use a safe getter.
ValidationError = getattr(icalendar, "ValidationError", Exception)


def _extract_categories(component: icalendar.cal.Component) -> List[str]:
    """Normalize CATEGORIES into a flat list of strings."""
    categories: List[str] = []
    cat_data = component.get("CATEGORIES", [])
    if not cat_data:
        return categories

    if isinstance(cat_data, list):
        for cat in cat_data:
            if hasattr(cat, "cats"):
                categories.extend([str(c) for c in cat.cats])
            else:
                categories.append(str(cat))
    else:
        if hasattr(cat_data, "cats"):
            categories.extend([str(c) for c in cat_data.cats])
        else:
            categories.append(str(cat_data))
    return categories


def _is_all_day_task(component: icalendar.cal.Component) -> bool:
    """Determine if a task uses date-only (all-day) fields."""
    for key in ("DTSTART", "DUE"):
        dt = component.get(key)
        if dt and hasattr(dt, "dt"):
            if not isinstance(dt.dt, datetime):
                return True
    return False


def parse_ical_to_task(ical_data: str | bytes, task_url: str, privacy: Optional[bool] = False) -> Task:
    """Parse iCalendar data into a Task object."""

    def _coerce_to_str(data: str | bytes) -> str:
        if isinstance(data, bytes):
            try:
                return data.decode("utf-8")
            except Exception:
                return data.decode("utf-8", "ignore")
        return str(data)

    try:
        calendar = icalendar.Calendar.from_ical(_coerce_to_str(ical_data))
        for component in calendar.walk():
            if component.name != "VTODO":
                continue

            attendees = parse_attendees(component)
            reminders = parse_reminders(component)
            categories = _extract_categories(component)

            description = str(component.get("DESCRIPTION", "")) if component.get("DESCRIPTION") else None
            if privacy is True:
                description = PRIVACY_MODE_TXT

            percent = component.get("PERCENT-COMPLETE")
            try:
                percent_val = int(percent) if percent is not None else None
            except Exception:
                percent_val = None

            priority = component.get("PRIORITY")
            try:
                priority_val = int(priority) if priority is not None else None
            except Exception:
                priority_val = None

            recurrence_raw = component.get("RRULE")
            recurrence_val = None
            if recurrence_raw:
                try:
                    if hasattr(recurrence_raw, "to_ical"):
                        ical_val = recurrence_raw.to_ical()
                        recurrence_val = ical_val.decode() if isinstance(ical_val, bytes) else str(ical_val)
                    else:
                        recurrence_val = str(recurrence_raw)
                except Exception:
                    recurrence_val = str(recurrence_raw)

            exdate_values = []
            if component.get("EXDATE"):
                raw_exdates = component.get("EXDATE")
                if not isinstance(raw_exdates, list):
                    raw_exdates = [raw_exdates]
                for ex in raw_exdates:
                    try:
                        if hasattr(ex, "dts"):
                            for dt_val in ex.dts:
                                exdate_values.append(format_datetime(dt_val))
                        else:
                            exdate_values.append(format_datetime(ex))
                    except Exception:
                        continue

            task = Task(
                uid=str(component.get("UID", "")),
                summary=str(component.get("SUMMARY", "")),
                description=description,
                status=str(component.get("STATUS", "")) if component.get("STATUS") else None,
                url=validate_and_correct_url(task_url) if task_url else None,
                start=format_datetime(component.get("DTSTART")),
                due=format_datetime(component.get("DUE")),
                completed=format_datetime(component.get("COMPLETED")),
                created=format_datetime(component.get("CREATED")),
                last_modified=format_datetime(component.get("LAST-MODIFIED")),
                all_day=_is_all_day_task(component),
                percent_complete=percent_val,
                priority=priority_val,
                organizer=str(component.get("ORGANIZER", "")).replace("mailto:", "") if component.get("ORGANIZER") else None,
                categories=categories if categories else None,
                attendees=attendees if attendees else None,
                reminders=reminders if reminders else None,
                recurrence=recurrence_val,
                recurrence_id=format_datetime(component.get("RECURRENCE-ID")) if component.get("RECURRENCE-ID") else None,
                exdate=exdate_values if exdate_values else None,
            )
            return task

        raise ValueError("No VTODO component found in the iCalendar data")

    except ValidationError as exc:
        raise ValueError(f"Invalid iCalendar format: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"Failed to parse iCalendar data: {exc}") from exc


def task_to_ical(task: Task) -> str:
    """Convert a Task object to an iCalendar string (VTODO)."""
    cal = icalendar.Calendar()
    cal.add("prodid", "-//Sabre NX//CalDAV Client//EN")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")

    vtodo = icalendar.Todo()
    vtodo.add("uid", task.uid)
    vtodo.add("summary", task.summary)

    if task.description:
        vtodo.add("description", task.description)
    if task.status:
        vtodo.add("status", task.status)
    if task.percent_complete is not None:
        vtodo.add("percent-complete", int(task.percent_complete))
    if task.priority is not None:
        vtodo.add("priority", int(task.priority))
    if task.categories:
        vtodo.add("categories", task.categories)

    now = datetime.now()
    vtodo.add("last-modified", now)
    if task.created:
        vtodo.add("created", datetime.fromisoformat(task.created))
    else:
        vtodo.add("created", now)

    if task.start:
        start_dt = datetime.fromisoformat(task.start)
        vtodo.add("dtstart", start_dt.date() if task.all_day else start_dt)
    if task.due:
        due_dt = datetime.fromisoformat(task.due)
        vtodo.add("due", due_dt.date() if task.all_day else due_dt)
    if task.completed:
        try:
            completed_dt = datetime.fromisoformat(task.completed)
            vtodo.add("completed", completed_dt)
        except Exception:
            pass

    if task.organizer:
        organizer = icalendar.vCalAddress(f"mailto:{task.organizer}")
        vtodo.add("organizer", organizer)

    if task.attendees:
        for attendee in task.attendees:
            attendee_prop = icalendar.vCalAddress(f"mailto:{attendee.email}")
            if attendee.name:
                attendee_prop.params["CN"] = attendee.name
            if attendee.role:
                attendee_prop.params["ROLE"] = attendee.role
            if attendee.status:
                attendee_prop.params["PARTSTAT"] = attendee.status
            if attendee.type:
                attendee_prop.params["CUTYPE"] = attendee.type
            vtodo.add("attendee", attendee_prop)

    if task.reminders:
        for reminder in task.reminders:
            valarm = icalendar.Alarm()
            valarm.add("action", reminder.type)
            valarm.add("trigger", reminder.trigger)
            if reminder.description:
                valarm.add("description", reminder.description)
            else:
                valarm.add("description", f"Reminder for: {task.summary}")
            vtodo.add_component(valarm)

    # Recurrence
    if task.recurrence:
        vtodo.add("rrule", task.recurrence)
    if task.recurrence_id:
        vtodo.add("recurrence-id", datetime.fromisoformat(task.recurrence_id))
    if task.exdate:
        ex_dates = []
        for ex in task.exdate:
            try:
                ex_dt = datetime.fromisoformat(ex.replace("Z", "+00:00"))
            except Exception:
                continue
            ex_dates.append(ex_dt.date() if task.all_day else ex_dt)
        if ex_dates:
            vtodo.add("exdate", ex_dates)

    cal.add_component(vtodo)
    return cal.to_ical().decode("utf-8")


def parse_ical_to_tasks(ical_data: str | bytes, task_url: str, privacy: Optional[bool] = False) -> List[Task]:
    """Parse iCalendar data into a list of Task objects (all VTODO components)."""

    def _coerce_to_str(data: str | bytes) -> str:
        if isinstance(data, bytes):
            try:
                return data.decode("utf-8")
            except Exception:
                return data.decode("utf-8", "ignore")
        return str(data)

    tasks: List[Task] = []
    try:
        calendar = icalendar.Calendar.from_ical(_coerce_to_str(ical_data))
        for component in calendar.walk():
            if component.name != "VTODO":
                continue
            try:
                task = parse_ical_to_task(component.to_ical(), task_url, privacy)
                if task:
                    tasks.append(task)
            except Exception as parse_error:
                raise ValueError(f"Error parsing VTODO component: {parse_error}")
        if not tasks:
            raise ValueError("No VTODO component found in the iCalendar data")
        return tasks
    except ValidationError as exc:
        raise ValueError(f"Invalid iCalendar format: {exc}") from exc
    except Exception as exc:
        raise ValueError(f"Failed to parse iCalendar data: {exc}") from exc
