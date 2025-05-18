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

JSON Example of an Event:
```json
{
  "uid": "550e8400-e29b-41d4-a716-446655440000",
  "summary": "Team Meeting",
  "description": "Weekly team sync-up",
  "location": "Conference Room A",
  "url": "https://nextcloud.example.com/remote.php/dav/calendars/username/personal/550e8400-e29b-41d4-a716-446655440000.ics",
  "start": "2025-04-21T14:00:00",
  "end": "2025-04-21T15:00:00",
  "all_day": false,
  "created": "2025-04-01T10:00:00",
  "last_modified": "2025-04-01T10:00:00",
  "status": "CONFIRMED",
  "organizer": "organizer@example.com",
  "categories": ["MEETING", "WORK"],
  "attendees": [
    {
      "email": "john.doe@example.com",
      "name": "John Doe",
      "role": "REQ-PARTICIPANT",
      "status": "ACCEPTED",
      "type": "INDIVIDUAL"
    }
  ],
  "reminders": [
    {
      "type": "DISPLAY",
      "trigger": "-PT15M",
      "description": "Reminder: Team Meeting"
    }
  ],
  "recurrence": "FREQ=WEEKLY;BYDAY=MO",
  "recurrence_id": null
}
```
"""

from typing import List, Optional, Literal, Union
import uuid
from datetime import datetime
from pydantic import BaseModel, Field

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
    url: Optional[str] = Field(None, description="URI of the event on the CalDAV server")
    
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
            return None
            
        if all_day:
            # For all-day events, return just the date part
            return dt_str.split('T')[0] if 'T' in dt_str else dt_str
        else:
            # For regular events, return a datetime object
            return datetime.fromisoformat(dt_str)

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
    
    JSON Example:
    ```json
    {
      "summary": "Meeting",
      "location": "Conference",
      "search_type": "anyof"
    }
    ```
    
    ```json
    {
      "summary": "Project",
      "attendee": "John",
      "search_type": "allof",
      "start_min": "2025-04-01T00:00:00",
      "start_max": "2025-04-30T23:59:59"
    }
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