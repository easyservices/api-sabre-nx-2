# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Event Models Module

This module defines the data models for calendar events and related entities used throughout the application.
It provides Pydantic models for type validation, serialization, and deserialization of event data
retrieved from or sent to CalDAV servers.

The module includes:
- Event: The main event model with calendar information
- Attendee: Attendee information for event participants
- Reminder: Reminder/alarm information for events
- EventSearchCriteria: Model for specifying search parameters

"""

from typing import List, Optional, Literal, Union
import uuid
from datetime import datetime
from pydantic import BaseModel, Field, model_validator
from src import logger

class Attendee(BaseModel):
    """
    Attendee information for an event.
    
    Represents a participant in a calendar event with their role and participation status.
    """
    email: str = Field(..., description="Email address of the attendee")
    name: Optional[str] = Field(None, description="Display name of the attendee")
    role: Optional[str] = Field(None, description="Role of the attendee (e.g., 'REQ-PARTICIPANT', 'OPT-PARTICIPANT', 'CHAIR')")
    status: Optional[str] = Field(None, description="Participation status (e.g., 'ACCEPTED', 'DECLINED', 'TENTATIVE', 'NEEDS-ACTION')")
    type: Optional[str] = Field(None, description="Type of attendee (e.g., 'INDIVIDUAL', 'GROUP', 'RESOURCE')")

class Reminder(BaseModel):
    """
    Reminder/alarm information for an event.
    
    Defines when and how a reminder should be triggered for an event.
    """
    type: str = Field(..., description="Type of reminder (e.g., 'DISPLAY', 'EMAIL', 'AUDIO')")
    trigger: str = Field(..., description="When the reminder should trigger (e.g., '-PT15M' for 15 minutes before)")
    description: Optional[str] = Field(None, description="Description or message for the reminder")

class Event(BaseModel):
    """
    Main event model representing a calendar event.
    
    This model contains all the information about an event, including timing details,
    location, participants, and recurrence information. It maps to a VEVENT component
    in the iCalendar format used by CalDAV.
    
    Example:
    ```python
    # Create an event with a manually specified UID
    event = Event(
        uid="123456",
        summary="Team Meeting",
        start="2025-04-21T14:00:00",
        end="2025-04-21T15:00:00",
        location="Conference Room A"
    )
    
    # Create an event with an auto-generated UUID
    event = Event(
        uid=Event.generate_uid(),
        summary="Project Kickoff",
        description="Initial meeting to discuss project goals",
        start="2025-05-01T10:00:00",
        end="2025-05-01T11:30:00",
        attendees=[
            Attendee(email="john.doe@example.com", name="John Doe", role="CHAIR")
        ]
    )
    ```
    """
    uid: str = Field(..., description="Unique identifier for the event")
    summary: str = Field(..., description="Title or summary of the event")
    description: Optional[str] = Field(None, description="Detailed description of the event")
    location: Optional[str] = Field(None, description="Location where the event takes place")
    url: Optional[str] = Field(None, description="URL of the event on the CalDAV server")
    
    # Timing information
    start: str = Field(..., description="Start time of the event in ISO format (YYYY-MM-DDTHH:MM:SS)")
    end: Optional[str] = Field(None, description="End time of the event in ISO format (YYYY-MM-DDTHH:MM:SS)")
    all_day: Optional[bool] = Field(False, description="Whether this is an all-day event")
    created: Optional[str] = Field(None, description="Creation time of the event in ISO format")
    last_modified: Optional[str] = Field(None, description="Last modification time of the event in ISO format")
    
    # Status and organization
    status: Optional[str] = Field(None, description="Status of the event (e.g., 'CONFIRMED', 'TENTATIVE', 'CANCELLED')")
    organizer: Optional[str] = Field(None, description="Email of the event organizer")
    categories: Optional[List[str]] = Field(None, description="List of categories/tags for the event")
    
    # Participants and notifications
    attendees: Optional[List[Attendee]] = Field(None, description="List of event attendees")
    reminders: Optional[List[Reminder]] = Field(None, description="List of reminders/alarms for the event")
    
    # Recurrence
    recurrence: Optional[str] = Field(None, description="Recurrence rule for repeating events (RRULE)")
    recurrence_id: Optional[str] = Field(None, description="For instances of recurring events, the original event's date/time")
    exdate: Optional[List[str]] = Field(None, description="List of ISO datetimes excluded from recurrence expansion")

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        if value.endswith("Z"):
            value = f"{value[:-1]}+00:00"
        return datetime.fromisoformat(value)

    @model_validator(mode="after")
    def check_datetimes(self):
        """Ensure datetime fields are ordered and timezone-consistent."""
        try:
            start_dt = self._parse_datetime(self.start)
        except Exception as exc:
            raise ValueError(f"Invalid start datetime: {self.start}") from exc
        if self.end:
            try:
                end_dt = self._parse_datetime(self.end)
            except Exception as exc:
                raise ValueError(f"Invalid end datetime: {self.end}") from exc
            if (start_dt.tzinfo is None) != (end_dt.tzinfo is None):
                raise ValueError("Event start and end must both include a timezone or neither")
            if end_dt <= start_dt:
                raise ValueError("Event end time must be after start time")
        return self
    
    @classmethod
    def generate_uid(cls) -> str:
        """
        Generate a unique identifier (UUID4) for an event.
        
        Returns:
            str: A string representation of a UUID4
        """
        return str(uuid.uuid4())
    
    def to_ical_datetime(self, dt_str: str, all_day: bool = False) -> Union[datetime, str]:
        """
        Convert an ISO format datetime string to the appropriate format for iCalendar.
        
        Args:
            dt_str: Datetime string in ISO format (YYYY-MM-DDTHH:MM:SS)
            all_day: Whether this is for an all-day event
            
        Returns:
            Union[datetime, str]: A datetime object for regular events, or a date string for all-day events
        """
        if not dt_str:
            return ""
            
        if all_day:
            # For all-day events, return just the date part
            return dt_str.split('T')[0] if 'T' in dt_str else dt_str
        else:
            # For regular events, return a datetime object
            return datetime.fromisoformat(dt_str)


class RecurrenceInstance(BaseModel):
    """
    Concrete occurrence of a recurring event after expansion.
    """
    recurrence_id: str = Field(..., description="Identifier of the specific occurrence (RECURRENCE-ID)")
    start: str = Field(..., description="Start datetime for this occurrence in ISO format")
    end: Optional[str] = Field(None, description="End datetime for this occurrence in ISO format")
    all_day: bool = Field(False, description="Whether this occurrence is all-day")
    source_uid: str = Field(..., description="UID of the recurring event")
    url: Optional[str] = Field(None, description="CalDAV resource URL associated with this occurrence")
    overrides_applied: bool = Field(False, description="True if this occurrence comes from an exception component")


class FriendlyRecurrence(BaseModel):
    """
    Human-friendly recurrence description to generate an RRULE.
    """
    frequency: Literal["DAILY", "WEEKLY", "MONTHLY", "YEARLY"] = Field(..., description="Recurrence frequency")
    interval: int = Field(1, ge=1, description="Interval between recurrences (e.g., every 2 weeks)")
    count: Optional[int] = Field(None, gt=0, description="Total number of occurrences")
    until: Optional[str] = Field(None, description="End of recurrence in ISO format")
    byweekday: Optional[List[Literal["MO", "TU", "WE", "TH", "FR", "SA", "SU"]]] = Field(None, description="Days of week for recurrence")
    bymonthday: Optional[List[int]] = Field(None, description="Days of month for recurrence")
    exclusions: Optional[List[str]] = Field(None, description="ISO datetimes to exclude (EXDATE)")


class RecurrencePreviewRequest(BaseModel):
    """
    Payload to preview or validate recurrence rules.
    """
    start: str = Field(..., description="Start datetime used as DTSTART for recurrence expansion")
    end: Optional[str] = Field(None, description="End datetime to derive duration; required for non-all-day when duration needed")
    all_day: bool = Field(False, description="Whether the base event is all-day")
    rrule: Optional[str] = Field(None, description="Raw RRULE string to preview")
    friendly: Optional[FriendlyRecurrence] = Field(None, description="Friendly recurrence description to generate RRULE")
    max_occurrences: int = Field(20, ge=1, le=500, description="Maximum occurrences to return for preview")

    @model_validator(mode="after")
    def ensure_rrule_source(self):
        """Require either raw rrule or friendly payload."""
        if not self.rrule and not self.friendly:
            raise ValueError("Either rrule or friendly must be provided")
        return self


class RecurrenceRuleRequest(BaseModel):
    """
    Payload to build/validate an RRULE from friendly fields.
    """
    friendly: FriendlyRecurrence


class RecurrenceExceptionRequest(BaseModel):
    """
    Payload to upsert an exception instance for a recurring event.
    """
    recurrence_id: str = Field(..., description="RECURRENCE-ID of the occurrence to override (ISO datetime)")
    summary: Optional[str] = Field(None, description="Override summary/title")
    description: Optional[str] = Field(None, description="Override description")
    location: Optional[str] = Field(None, description="Override location")
    status: Optional[str] = Field(None, description="Override status")
    start: Optional[str] = Field(None, description="Override start datetime")
    end: Optional[str] = Field(None, description="Override end datetime")
    all_day: Optional[bool] = Field(None, description="Override all-day flag")
    categories: Optional[List[str]] = Field(None, description="Override categories")
    attendees: Optional[List[Attendee]] = Field(None, description="Override attendees list")
    reminders: Optional[List[Reminder]] = Field(None, description="Override reminders list")

    @model_validator(mode="after")
    def ensure_override_fields(self):
        """Ensure at least one override besides recurrence_id is provided."""
        overrides = self.model_dump(exclude={"recurrence_id"}, exclude_none=True)
        if not overrides:
            raise ValueError("At least one override field must be provided")
        return self


class RecurrenceSkipRequest(BaseModel):
    """
    Payload to skip/remove specific recurrence instances by adding EXDATE entries.
    """
    recurrence_ids: List[str] = Field(..., min_length=1, description="List of RECURRENCE-ID values (ISO datetimes) to exclude")
    reason: Optional[str] = Field(None, description="Optional reason for audit/logging")


class RecurrencePreviewResponse(BaseModel):
    """
    Response for recurrence preview/build endpoints.
    """
    rrule: str
    occurrences: List[RecurrenceInstance]
    excluded: List[str] = Field(default_factory=list)

class EventSearchCriteria(BaseModel):
    """
    Search criteria for events.
    
    This model defines the fields that can be used to search for events in a CalDAV server.
    All fields are optional and case-insensitive partial matches are used for string fields.
    
    The search_type field determines whether to use OR logic ("anyof") or AND logic ("allof")
    when multiple search criteria are provided.
    
    Python Example:
    ```python
    # Search for events with "Meeting" in the summary OR "Conference" in the location
    criteria = EventSearchCriteria(
        summary="Meeting",
        location="Conference",
        search_type="anyof"
    )
    
    # Search for events with "Project" in the summary AND "John" as an attendee
    criteria = EventSearchCriteria(
        summary="Project",
        attendee="John",
        search_type="allof"
    )
    ```
    """
    uid: Optional[str] = Field(None, description="Search by event UID (case-insensitive partial match)")
    summary: Optional[str] = Field(None, description="Search by event summary/title (case-insensitive partial match)")
    description: Optional[str] = Field(None, description="Search by event description (case-insensitive partial match)")
    location: Optional[str] = Field(None, description="Search by event location (case-insensitive partial match)")
    category: Optional[str] = Field(None, description="Search by event category/tag (case-insensitive partial match)")
    attendee: Optional[str] = Field(None, description="Search by attendee name or email (case-insensitive partial match)")
    
    # Date range filters
    start_min: Optional[str] = Field(None, description="Minimum start date/time (inclusive) in ISO format")
    start_max: Optional[str] = Field(None, description="Maximum start date/time (inclusive) in ISO format")
    end_min: Optional[str] = Field(None, description="Minimum end date/time (inclusive) in ISO format")
    end_max: Optional[str] = Field(None, description="Maximum end date/time (inclusive) in ISO format")
    
    # Other filters
    all_day: Optional[bool] = Field(None, description="Filter for all-day events")
    status: Optional[str] = Field(None, description="Filter by event status (e.g., 'CONFIRMED', 'TENTATIVE', 'CANCELLED')")
    
    search_type: Optional[Literal["anyof", "allof"]] = Field(
        default="anyof",
        description="Search logic: 'anyof' (OR) means any criteria can match, 'allof' (AND) means all criteria must match"
    )
    
    def to_dict(self):
        """
        Convert to dictionary, excluding None values and search_type.
        
        Returns:
            dict: Dictionary containing only the non-None search criteria fields,
                  excluding the search_type field which is handled separately.
        """
        return {k: v for k, v in self.model_dump().items()
                if v is not None and k != "search_type"}
