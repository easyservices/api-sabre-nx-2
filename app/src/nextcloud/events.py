# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Nextcloud CalDAV events module.

This module provides functions to interact with Nextcloud CalDAV events.
It includes functionality to retrieve and search events from a Nextcloud server.
"""

from typing import Optional, List
from fastapi.security import HTTPBasicCredentials

from src.common.libs.helpers import gen_nxtcloud_url_calendar
from src.common.sec import gen_basic_auth_header, authenticate_with_nextcloud
from src.models.event import Event
from src.nextcloud.libs.caldav_helpers import (
    parse_ical_to_event,
    parse_caldav_xml_response,
    event_to_ical,
    parse_events_from_response
)
from src.nextcloud.libs.carddav_helpers import validate_and_correct_url
from src.nextcloud.libs.dav_clients import CalDavClient
from src import logger

async def get_event_by_uid(credentials: HTTPBasicCredentials, uid: str, calendar_name: Optional[str] = None, privacy: Optional[bool] = False) -> Optional[Event]:
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
        
    user_info = authenticate_with_nextcloud(credentials)
    logger.debug(f"User credentials: {user_info}")
    
    caldav_url = gen_nxtcloud_url_calendar(user_info['id'], calendar_name)
    logger.debug(f"get_event_by_uid: caldav_url: {caldav_url}")
    
    auth_header = gen_basic_auth_header(credentials.username, credentials.password)
    client = CalDavClient(caldav_url, auth_header)
    # Validate the UID
    if not uid:
        raise ValueError("Event UID must be provided for retrieval")
    
    # Construct the URL for the event
    event_filename = f"{uid}.ics"
    event_url = client.build_url(event_filename)
    
    logger.debug(f"Retrieving event at URL: {event_url}")
    
    ical_text = await client.get_event(event_url)
    if ical_text is None:
        return None
    
    return parse_ical_to_event(ical_text, event_url, privacy)


async def get_events_by_time_range(
    credentials: HTTPBasicCredentials,
    start_datetime: str,
    end_datetime: str,
    calendar_name: Optional[str],
    privacy: Optional[bool] = False
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
        
    user_info = authenticate_with_nextcloud(credentials)
    logger.debug(f"User credentials: {user_info}")
    
    caldav_url = gen_nxtcloud_url_calendar(user_info['id'], calendar_name)
    logger.debug(f"get_events_by_time_range: caldav_url: {caldav_url}")
    
    auth_header = gen_basic_auth_header(credentials.username, credentials.password)
    client = CalDavClient(caldav_url, auth_header)
    # Validate the datetime parameters
    if not start_datetime or not end_datetime:
        raise ValueError("Both start and end datetime must be provided")
    
    logger.debug(f"Retrieving events between {start_datetime} and {end_datetime} from {client.base_url}")
    
    response_text = await client.report_time_range(start_datetime, end_datetime)
    
    # Parse the XML response
    calendar_items = parse_caldav_xml_response(response_text)
    
    # Convert each calendar item to an Event object using the new helper function
    events = parse_events_from_response(calendar_items, privacy)
    
    # Sort events by start datetime
    events.sort(key=lambda event: event.start if event.start else "")
    
    logger.debug(f"Sorted {len(events)} events by start datetime")
    
    return events


async def create_event(credentials: HTTPBasicCredentials, event: Event, calendar_name: Optional[str] = None) -> Event:
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
        
    user_info = authenticate_with_nextcloud(credentials)
    logger.debug(f"User credentials: {user_info}")
    
    caldav_url = gen_nxtcloud_url_calendar(user_info['id'], calendar_name)
    logger.debug(f"create_event: caldav_url: {caldav_url}")
    
    auth_header = gen_basic_auth_header(credentials.username, credentials.password)
    client = CalDavClient(caldav_url, auth_header)
    # Validate the event
    if not event.uid:
        # Generate a new UID if not provided
        event.uid = Event.generate_uid()
    
    if not event.summary:
        raise ValueError("Event summary (title) is required")
    
    if not event.start:
        raise ValueError("Event start time is required")
    
    # Construct the URL for the event
    event_filename = f"{event.uid}.ics"
    event_url = client.build_url(event_filename)
    
    logger.debug(f"Creating event at URL: {event_url}")
    
    # Convert the Event object to iCalendar format
    ical_data = event_to_ical(event)
    
    logger.debug(f"iCalendar data:\n{ical_data}")
    
    await client.create_event(event_url, ical_data)
    
    # Update the event URL with validation
    event.url = validate_and_correct_url(event_url)
    
    logger.debug(f"Event created successfully with UID: {event.uid}")
    
    return event


async def update_event(credentials: HTTPBasicCredentials, event: Event, calendar_name: Optional[str] = None) -> Event:
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
        
    user_info = authenticate_with_nextcloud(credentials)
    logger.debug(f"User credentials: {user_info}")
    
    caldav_url = gen_nxtcloud_url_calendar(user_info['id'], calendar_name)
    logger.debug(f"update_event: caldav_url: {caldav_url}")
    
    auth_header = gen_basic_auth_header(credentials.username, credentials.password)
    client = CalDavClient(caldav_url, auth_header)
    # Validate the event
    if not event.uid:
        raise ValueError("Event UID is required for updates")
    
    if not event.summary:
        raise ValueError("Event summary (title) is required")
    
    if not event.start:
        raise ValueError("Event start time is required")
    
    # Construct the URL for the event
    event_filename = f"{event.uid}.ics"
    event_url = client.build_url(event_filename)
    
    logger.debug(f"Updating event at URL: {event_url}")
    
    # Optional: Check if the event exists
    existing_event = await get_event_by_uid(credentials, event.uid, calendar_name)
    if not existing_event:
        raise ValueError(f"Event with UID {event.uid} not found")
    
    # Preserve certain fields from the existing event if not provided in the update
    if not event.url:
        event.url = validate_and_correct_url(existing_event.url) if existing_event.url else None
    
    if not event.created:
        event.created = existing_event.created
    
    # Convert the Event object to iCalendar format
    ical_data = event_to_ical(event)
    
    logger.debug(f"iCalendar data for update:\n{ical_data}")
    
    await client.update_event(event_url, ical_data)
    
    # Update the event URL (in case it changed) with validation
    event.url = validate_and_correct_url(event_url)
    
    logger.debug(f"Event updated successfully with UID: {event.uid}")
    
    return event


async def delete_event(credentials: HTTPBasicCredentials, uid: str, calendar_name: Optional[str] = None) -> bool:
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
    logger.debug(f"delete_event: deleting event with UID: {uid}")
        
    user_info = authenticate_with_nextcloud(credentials)
    logger.debug(f"User credentials: {user_info}")
    
    caldav_url = gen_nxtcloud_url_calendar(user_info['id'], calendar_name)
    logger.debug(f"delete_event: caldav_url: {caldav_url}")
    
    auth_header = gen_basic_auth_header(credentials.username, credentials.password)
    client = CalDavClient(caldav_url, auth_header)
    # Validate the UID
    if not uid:
        raise ValueError("Event UID must be provided for deletion")
    
    # Construct the URL for the event
    event_filename = f"{uid}.ics"
    event_url = client.build_url(event_filename)
    
    logger.debug(f"Deleting event at URL: {event_url}")
    
    # Optional: Check if the event exists
    existing_event = await get_event_by_uid(credentials, uid, calendar_name)
    if not existing_event:
        logger.debug(f"Event with UID {uid} not found, nothing to delete")
        return False
    
    deleted = await client.delete_event(event_url)
    if not deleted:
        logger.debug(f"Event with UID {uid} not found on server")
        return False
    
    logger.debug(f"Event deleted successfully with UID: {uid}")
    return True
