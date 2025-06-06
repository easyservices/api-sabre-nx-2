# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Helper functions for CalDAV operations.

This module provides utility functions for working with CalDAV,
including iCalendar parsing, event formatting, and component processing.
"""

from fastapi import HTTPException
from typing import List, Dict, Any, Optional
import icalendar
import xml.etree.ElementTree as ET
from datetime import datetime

from src.models.event import Event, Attendee, Reminder

def parse_ical_to_event(ical_data: str, event_url: str, privacy: Optional[bool] = False) -> Event:
    """
    Parse iCalendar data into an Event object.
    
    Args:
        ical_data (str): The iCalendar data as a string.
        event_url (str): The URL of the event.
        
    Returns:
        Event: An Event object containing the parsed event data.
        
    Raises:
        ValueError: If the iCalendar data cannot be parsed.
    """
    try:
        # Parse the iCalendar data
        calendar = icalendar.Calendar.from_ical(ical_data)
        
        # Extract the event component
        for component in calendar.walk():
            if component.name == "VEVENT":
                try:
                    # Parse attendees
                    attendees = parse_attendees(component)
                    
                    # Parse reminders/alarms
                    reminders = parse_reminders(component)
                    
                    # Extract categories
                    categories = []
                    if component.get("CATEGORIES"):
                        cat_data = component.get("CATEGORIES", [])
                        if isinstance(cat_data, list):
                            categories = [str(cat) for cat in cat_data]
                        else:
                            categories = [str(cat_data)]

                    # Handle privacy setting
                    description = str(component.get("DESCRIPTION", "")) if component.get("DESCRIPTION") else None
                    if privacy is True:
                        description = None
                    
                    # Create the Event object
                    event = Event(
                        uid=str(component.get("UID", "")),
                        summary=str(component.get("SUMMARY", "")),
                        description=description,
                        location=str(component.get("LOCATION", "")) if component.get("LOCATION") else None,
                        url=event_url,
                        status=str(component.get("STATUS", "")) if component.get("STATUS") else None,
                        organizer=str(component.get("ORGANIZER", "")).replace("mailto:", "") if component.get("ORGANIZER") else None,
                        categories=categories if categories else None,
                        created=format_datetime(component.get("CREATED")),
                        last_modified=format_datetime(component.get("LAST-MODIFIED")),
                        start=format_datetime(component.get("DTSTART")),
                        end=format_datetime(component.get("DTEND")),
                        all_day=is_all_day_event(component),
                        recurrence=str(component.get("RRULE", "")) if component.get("RRULE") else None,
                        recurrence_id=format_datetime(component.get("RECURRENCE-ID")) if component.get("RECURRENCE-ID") else None,
                        attendees=attendees if attendees else None,
                        reminders=reminders if reminders else None
                    )
                    return event
                except Exception as parse_error:
                    raise ValueError(f"Error parsing VEVENT component: {str(parse_error)}")
        
        # If no VEVENT component was found
        raise ValueError("No VEVENT component found in the iCalendar data")
        
    except icalendar.parser.InvalidCalendar as e:
        raise ValueError(f"Invalid iCalendar format: {str(e)}")
    except Exception as e:
        raise ValueError(f"Failed to parse iCalendar data: {str(e)}")

def format_datetime(dt_value) -> Optional[str]:
    """
    Format a datetime value from an iCalendar component.
    
    Args:
        dt_value: The datetime value from an iCalendar component.
        
    Returns:
        Optional[str]: The formatted datetime string or None if the value is not provided.
    """
    if not dt_value:
        return None
    
    try:
        # Handle different types of datetime values
        if hasattr(dt_value, 'dt'):
            if isinstance(dt_value.dt, datetime):
                # Format as ISO 8601
                return dt_value.dt.isoformat()
            else:
                # For date-only values
                return str(dt_value.dt)
        else:
            # Handle case where dt_value is already a string or datetime
            if isinstance(dt_value, datetime):
                return dt_value.isoformat()
            else:
                return str(dt_value)
    except Exception as e:
        # If all else fails, try to convert to string
        return str(dt_value) if dt_value else None

def is_all_day_event(component) -> bool:
    """
    Determine if an event is an all-day event.
    
    Args:
        component: The iCalendar VEVENT component.
        
    Returns:
        bool: True if the event is an all-day event, False otherwise.
    """
    dtstart = component.get("DTSTART")
    if dtstart:
        try:
            if hasattr(dtstart, 'dt'):
                # If DTSTART is a date (not a datetime), it's an all-day event
                return not isinstance(dtstart.dt, datetime)
            else:
                # Handle case where dtstart doesn't have dt attribute
                return False
        except Exception:
            # If we can't determine, assume it's not all-day
            return False
    return False

def parse_attendees(component) -> List[Attendee]:
    """
    Parse attendees from an iCalendar VEVENT component.
    
    Args:
        component: The iCalendar VEVENT component.
        
    Returns:
        List[Attendee]: A list of Attendee objects containing attendee information.
    """
    attendees = []
    attendee_data = component.get("ATTENDEE", [])
    
    # Handle case where there's only one attendee (returns single item instead of list)
    if not isinstance(attendee_data, list):
        attendee_data = [attendee_data]
    
    for attendee in attendee_data:
        # Extract attendee properties
        email = str(attendee).replace("mailto:", "")
        
        # Check if attendee has params attribute (some iCalendar implementations return strings)
        if hasattr(attendee, 'params'):
            role = str(attendee.params.get("ROLE", "")) if "ROLE" in attendee.params else None
            status = str(attendee.params.get("PARTSTAT", "")) if "PARTSTAT" in attendee.params else None
            attendee_type = str(attendee.params.get("CUTYPE", "")) if "CUTYPE" in attendee.params else None
            name = str(attendee.params.get("CN", "")) if "CN" in attendee.params else None
        else:
            # If no params attribute, set all optional fields to None
            role = None
            status = None
            attendee_type = None
            name = None
        
        # Create Attendee object
        attendee_obj = Attendee(
            email=email,
            role=role if role else None,
            status=status if status else None,
            type=attendee_type if attendee_type else None,
            name=name if name else None
        )
        attendees.append(attendee_obj)
    return attendees

def parse_reminders(component) -> List[Reminder]:
    """
    Parse reminders/alarms from an iCalendar VEVENT component.
    
    Args:
        component: The iCalendar VEVENT component.
        
    Returns:
        List[Reminder]: A list of Reminder objects containing alarm information.
    """
    reminders = []
    for alarm in component.walk("VALARM"):
        # Extract alarm properties
        action = str(alarm.get("ACTION", ""))
        trigger = str(alarm.get("TRIGGER", ""))
        description = str(alarm.get("DESCRIPTION", "")) if alarm.get("DESCRIPTION") else None
        
        # Create Reminder object
        reminder = Reminder(
            type=action,
            trigger=trigger,
            description=description
        )
        reminders.append(reminder)
    return reminders

def handle_caldav_response_status(status_code: int, response_text: str) -> None:
    """
    Handle HTTP status codes and raise appropriate exceptions for CalDAV responses.
    
    Args:
        status_code (int): HTTP status code.
        response_text (str): Response text from the server.
        
    Raises:
        HTTPException: For authentication, authorization, server, or parsing errors.
    """
    if status_code == 401:
        raise HTTPException(status_code=401, detail="Authentication failed")
    if status_code == 403:
        raise HTTPException(status_code=403, detail="Access forbidden")
    if status_code == 404:
        raise HTTPException(status_code=404, detail="Calendar not found")
    if status_code >= 500:
        raise HTTPException(status_code=500, detail=f"Server error: {response_text}")
    if status_code != 207 and status_code != 200:
        raise HTTPException(status_code=status_code, detail=f"Server returned unexpected status: {response_text}")

def create_caldav_request_headers(auth_header: str) -> Dict[str, str]:
    """
    Create headers for the CalDAV request.
    
    Args:
        auth_header (str): HTTP Authorization header value.
        
    Returns:
        Dict[str, str]: Headers dictionary for the request.
    """
    return {
        "Depth": "1",
        "Content-Type": "application/xml; charset=utf-8",
        "authorization": auth_header
    }

def create_time_range_filter_xml(start_datetime: str, end_datetime: str) -> str:
    """
    Create a CalDAV time-range filter XML string.
    
    Args:
        start_datetime (str): Start datetime in ISO format (YYYY-MM-DDTHH:MM:SS).
        end_datetime (str): End datetime in ISO format (YYYY-MM-DDTHH:MM:SS).
        
    Returns:
        str: XML string for the time-range filter.
    """
    # Convert ISO format to CalDAV format (YYYYMMDDTHHMMSSZ)
    start = datetime.fromisoformat(start_datetime).strftime("%Y%m%dT%H%M%SZ")
    end = datetime.fromisoformat(end_datetime).strftime("%Y%m%dT%H%M%SZ")
    
    return f"""
        <c:time-range start="{start}" end="{end}"/>
    """

def create_calendar_query_xml(start_datetime: str, end_datetime: str) -> str:
    """
    Create the XML data for a CalDAV calendar-query request with time range filter.
    
    Args:
        start_datetime (str): Start datetime in ISO format (YYYY-MM-DDTHH:MM:SS).
        end_datetime (str): End datetime in ISO format (YYYY-MM-DDTHH:MM:SS).
        
    Returns:
        str: Complete XML data for the request.
    """
    time_range_filter = create_time_range_filter_xml(start_datetime, end_datetime)
    
    return f"""<?xml version="1.0" encoding="utf-8" ?>
<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
    <d:prop>
        <d:getetag/>
        <c:calendar-data/>
    </d:prop>
    <c:filter>
        <c:comp-filter name="VCALENDAR">
            <c:comp-filter name="VEVENT">
                {time_range_filter}
            </c:comp-filter>
        </c:comp-filter>
    </c:filter>
</c:calendar-query>"""

def parse_caldav_xml_response(response_text: str) -> List[Dict[str, Any]]:
    """
    Parse the XML response from the CalDAV server.
    
    Args:
        response_text (str): XML response text from the server.
        
    Returns:
        List[Dict[str, Any]]: List of dictionaries containing href and calendar_data.
    """
    result = []
    root = ET.fromstring(response_text)
    
    for response_element in root.findall('.//{DAV:}response'):
        href_element = response_element.find('.//{DAV:}href')
        calendar_data_element = response_element.find('.//{urn:ietf:params:xml:ns:caldav}calendar-data')
        
        if calendar_data_element is not None and calendar_data_element.text:
            result.append({
                'href': href_element.text if href_element is not None else None,
                'calendar_data': calendar_data_element.text
            })
    
    return result


def event_to_ical(event: Event) -> str:
    """
    Convert an Event object to an iCalendar string.
    
    This function creates an iCalendar representation of an Event object using the icalendar library.
    It handles all the fields in the Event model, including:
    - UID
    - Summary (title)
    - Description
    - Location
    - Start and end times
    - Status
    - Organizer
    - Categories
    - Attendees
    - Reminders/alarms
    - Recurrence rules
    
    Args:
        event (Event): The Event object to convert.
        
    Returns:
        str: iCalendar string representation of the Event.
    """
    # Create a new iCalendar
    cal = icalendar.Calendar()
    cal.add('prodid', '-//Sabre NX//CalDAV Client//EN')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    
    # Create the event component
    vevent = icalendar.Event()
    
    # Add UID (required)
    vevent.add('uid', event.uid)
    
    # Add summary/title (required)
    vevent.add('summary', event.summary)
    
    # Add description (optional)
    if event.description:
        vevent.add('description', event.description)
    
    # Add location (optional)
    if event.location:
        vevent.add('location', event.location)
    
    # Add start time (required)
    start_dt = datetime.fromisoformat(event.start)
    if event.all_day:
        # For all-day events, use date component only
        vevent.add('dtstart', start_dt.date())
    else:
        vevent.add('dtstart', start_dt)
    
    # Add end time (optional but recommended)
    if event.end:
        end_dt = datetime.fromisoformat(event.end)
        if event.all_day:
            # For all-day events, use date component only
            vevent.add('dtend', end_dt.date())
        else:
            vevent.add('dtend', end_dt)
    
    # Add status (optional)
    if event.status:
        vevent.add('status', event.status)
    
    # Add organizer (optional)
    if event.organizer:
        organizer = icalendar.vCalAddress(f"mailto:{event.organizer}")
        vevent.add('organizer', organizer)
    
    # Add categories (optional)
    if event.categories:
        vevent.add('categories', event.categories)
    
    # Add creation time (optional)
    if not event.created:
        vevent.add('created', datetime.now())
    else:
        vevent.add('created', datetime.fromisoformat(event.created))
    
    # Add last modified time (optional)
    vevent.add('last-modified', datetime.now())
    
    # Add recurrence rule (optional)
    if event.recurrence:
        vevent.add('rrule', event.recurrence)
    
    # Add recurrence ID (optional)
    if event.recurrence_id:
        vevent.add('recurrence-id', datetime.fromisoformat(event.recurrence_id))
    
    # Add attendees (optional)
    if event.attendees:
        for attendee in event.attendees:
            attendee_prop = icalendar.vCalAddress(f"mailto:{attendee.email}")
            
            # Add attendee parameters
            if attendee.name:
                attendee_prop.params['CN'] = attendee.name
            if attendee.role:
                attendee_prop.params['ROLE'] = attendee.role
            if attendee.status:
                attendee_prop.params['PARTSTAT'] = attendee.status
            if attendee.type:
                attendee_prop.params['CUTYPE'] = attendee.type
            
            vevent.add('attendee', attendee_prop)
    
    # Add reminders/alarms (optional)
    if event.reminders:
        for reminder in event.reminders:
            valarm = icalendar.Alarm()
            valarm.add('action', reminder.type)
            valarm.add('trigger', reminder.trigger)
            
            if reminder.description:
                valarm.add('description', reminder.description)
            else:
                valarm.add('description', f"Reminder for: {event.summary}")
            
            vevent.add_component(valarm)
    
    # Add the event to the calendar
    cal.add_component(vevent)
    
    # Return the serialized iCalendar
    return cal.to_ical().decode('utf-8')


def create_caldav_event_headers(auth_header: str) -> Dict[str, str]:
    """
    Create headers for the CalDAV PUT request to create or update an event.
    
    Args:
        auth_header (str): HTTP Authorization header value.
        
    Returns:
        Dict[str, str]: Headers dictionary for the request.
    """
    return {
        "Content-Type": "text/calendar; charset=utf-8",
        "authorization": auth_header
    }