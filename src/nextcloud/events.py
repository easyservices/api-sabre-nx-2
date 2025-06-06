# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Nextcloud CalDAV events module.

This module provides functions to interact with Nextcloud CalDAV events.
It includes functionality to retrieve and search events from a Nextcloud server.
"""

from fastapi import HTTPException
from typing import Optional, List
import aiohttp
from fastapi.security import HTTPBasicCredentials

from src.common.libs.helpers import gen_nxtcloud_url_calendar
from src.common.sec import gen_basic_auth_header, authenticate_with_nextcloud
from src.models.event import Event
from src.nextcloud import API_ERR_CONNECTION_ERROR
from src.nextcloud.libs.caldav_helpers import (
    parse_ical_to_event,
    handle_caldav_response_status,
    create_caldav_request_headers,
    create_calendar_query_xml,
    parse_caldav_xml_response,
    event_to_ical,
    create_caldav_event_headers
)

# Constants
IS_DEBUG = True

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
    if IS_DEBUG:
        print(f"get_event_by_uid: credentials: {credentials}")
        
    user_info = authenticate_with_nextcloud(credentials)
    if IS_DEBUG:
        print(f"get_event_by_uid: User info: {user_info}")
    
    caldav_url = gen_nxtcloud_url_calendar(user_info['id'], calendar_name)
    if IS_DEBUG:
        print(f"get_event_by_uid: caldav_url: {caldav_url}")
    
    auth_header = gen_basic_auth_header(credentials.username, credentials.password)
    # Validate the UID
    if not uid:
        raise ValueError("Event UID must be provided for retrieval")
    
    # Construct the URL for the event
    # For CalDAV, the URL structure might be different from CardDAV
    # Typically, it would be something like: /remote.php/dav/calendars/username/calendar_name/event_uid.ics
    base_url = caldav_url if caldav_url.endswith('/') else f"{caldav_url}/"
    event_filename = f"{uid}.ics"
    event_url = f"{base_url}{event_filename}"
    
    if IS_DEBUG:
        print(f"Retrieving event at URL: {event_url}")
    
    # Create headers for the GET request
    headers = {
        "authorization": auth_header,
        "Content-Type": "text/calendar; charset=utf-8"
    }
    
    # Send the GET request
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(event_url, headers=headers) as response:
                status_code = response.status
                
                # If event not found, return None instead of raising an exception
                if status_code == 404:
                    return None
                
                response_text = await response.text()
                
                # Handle other error responses
                if status_code != 200:
                    handle_caldav_response_status(status_code, response_text)
                
                # Parse iCalendar data to dictionary
                return parse_ical_to_event(response_text, event_url, privacy)
                
        except aiohttp.ClientError as e:
            raise HTTPException(status_code=500, detail=f"{API_ERR_CONNECTION_ERROR}: {str(e)}")


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
    if IS_DEBUG:
        print(f"get_events_by_time_range: credentials: {credentials}")
        
    user_info = authenticate_with_nextcloud(credentials)
    if IS_DEBUG:
        print(f"get_events_by_time_range: User info: {user_info}")
    
    caldav_url = gen_nxtcloud_url_calendar(user_info['id'], calendar_name)
    if IS_DEBUG:
        print(f"get_events_by_time_range: caldav_url: {caldav_url}")
    
    auth_header = gen_basic_auth_header(credentials.username, credentials.password)
    # Validate the datetime parameters
    if not start_datetime or not end_datetime:
        raise ValueError("Both start and end datetime must be provided")
    
    # Ensure the URL ends with a slash
    base_url = caldav_url if caldav_url.endswith('/') else f"{caldav_url}/"
    
    if IS_DEBUG:
        print(f"Retrieving events between {start_datetime} and {end_datetime} from {base_url}")
    
    # Create headers for the REPORT request
    headers = create_caldav_request_headers(auth_header)
    
    # Create the XML payload for the calendar-query with time range filter
    xml_data = create_calendar_query_xml(start_datetime, end_datetime)
    
    # Send the REPORT request
    async with aiohttp.ClientSession() as session:
        try:
            async with session.request("REPORT", base_url, headers=headers, data=xml_data) as response:
                status_code = response.status
                response_text = await response.text()
                
                # Handle error responses
                if status_code != 207:  # 207 Multi-Status is the expected response
                    handle_caldav_response_status(status_code, response_text)
                
                # Parse the XML response
                calendar_items = parse_caldav_xml_response(response_text)
                
                # Convert each calendar item to an Event object
                events = []
                for item in calendar_items:
                    href = item.get('href')
                    calendar_data = item.get('calendar_data')
                    
                    if calendar_data:
                        try:
                            event = parse_ical_to_event(calendar_data, href, privacy)
                            events.append(event)
                        except ValueError as e:
                            if IS_DEBUG:
                                print(f"Error parsing event: {e}")
                
                # Sort events by start datetime
                events.sort(key=lambda event: event.start if event.start else "")
                
                if IS_DEBUG:
                    print(f"Sorted {len(events)} events by start datetime")
                
                return events
                
        except aiohttp.ClientError as e:
            raise HTTPException(status_code=500, detail=f"{API_ERR_CONNECTION_ERROR}: {str(e)}")


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
    if IS_DEBUG:
        print(f"create_event: credentials: {credentials}")
        
    user_info = authenticate_with_nextcloud(credentials)
    if IS_DEBUG:
        print(f"create_event: User info: {user_info}")
    
    caldav_url = gen_nxtcloud_url_calendar(user_info['id'], calendar_name)
    if IS_DEBUG:
        print(f"create_event: caldav_url: {caldav_url}")
    
    auth_header = gen_basic_auth_header(credentials.username, credentials.password)
    # Validate the event
    if not event.uid:
        # Generate a new UID if not provided
        event.uid = Event.generate_uid()
    
    if not event.summary:
        raise ValueError("Event summary (title) is required")
    
    if not event.start:
        raise ValueError("Event start time is required")
    
    # Ensure the URL ends with a slash
    base_url = caldav_url if caldav_url.endswith('/') else f"{caldav_url}/"
    
    # Construct the URL for the event
    event_filename = f"{event.uid}.ics"
    event_url = f"{base_url}{event_filename}"
    
    if IS_DEBUG:
        print(f"Creating event at URL: {event_url}")
    
    # Convert the Event object to iCalendar format
    ical_data = event_to_ical(event)
    
    if IS_DEBUG:
        print(f"iCalendar data:\n{ical_data}")
    
    # Create headers for the PUT request
    headers = create_caldav_event_headers(auth_header)
    
    # Send the PUT request
    async with aiohttp.ClientSession() as session:
        try:
            async with session.put(event_url, headers=headers, data=ical_data) as response:
                status_code = response.status
                
                # If we get a response, try to read the body
                response_text = await response.text() if response.content else ""
                
                # Handle error responses
                if status_code not in (201, 204):  # 201 Created or 204 No Content are success codes
                    handle_caldav_response_status(status_code, response_text)
                
                # Update the event URL
                event.url = event_url
                
                if IS_DEBUG:
                    print(f"Event created successfully with UID: {event.uid}")
                
                return event
                
        except aiohttp.ClientError as e:
            raise HTTPException(status_code=500, detail=f"{API_ERR_CONNECTION_ERROR}: {str(e)}")


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
    if IS_DEBUG:
        print(f"update_event: credentials: {credentials}")
        
    user_info = authenticate_with_nextcloud(credentials)
    if IS_DEBUG:
        print(f"update_event: User info: {user_info}")
    
    caldav_url = gen_nxtcloud_url_calendar(user_info['id'], calendar_name)
    if IS_DEBUG:
        print(f"update_event: caldav_url: {caldav_url}")
    
    auth_header = gen_basic_auth_header(credentials.username, credentials.password)
    # Validate the event
    if not event.uid:
        raise ValueError("Event UID is required for updates")
    
    if not event.summary:
        raise ValueError("Event summary (title) is required")
    
    if not event.start:
        raise ValueError("Event start time is required")
    
    # Ensure the URL ends with a slash
    base_url = caldav_url if caldav_url.endswith('/') else f"{caldav_url}/"
    
    # Construct the URL for the event
    event_filename = f"{event.uid}.ics"
    event_url = f"{base_url}{event_filename}"
    
    if IS_DEBUG:
        print(f"Updating event at URL: {event_url}")
    
    # Optional: Check if the event exists
    existing_event = await get_event_by_uid(credentials, event.uid, calendar_name)
    if not existing_event:
        raise ValueError(f"Event with UID {event.uid} not found")
    
    # Preserve certain fields from the existing event if not provided in the update
    if not event.url:
        event.url = existing_event.url
    
    if not event.created:
        event.created = existing_event.created
    
    # Convert the Event object to iCalendar format
    ical_data = event_to_ical(event)
    
    if IS_DEBUG:
        print(f"iCalendar data for update:\n{ical_data}")
    
    # Create headers for the PUT request
    headers = create_caldav_event_headers(auth_header)
    
    # Send the PUT request
    async with aiohttp.ClientSession() as session:
        try:
            async with session.put(event_url, headers=headers, data=ical_data) as response:
                status_code = response.status
                
                # If we get a response, try to read the body
                response_text = await response.text() if response.content else ""
                
                # Handle error responses
                if status_code not in (200, 204):  # 200 OK or 204 No Content are success codes for updates
                    handle_caldav_response_status(status_code, response_text)
                
                # Update the event URL (in case it changed)
                event.url = event_url
                
                if IS_DEBUG:
                    print(f"Event updated successfully with UID: {event.uid}")
                
                return event
                
        except aiohttp.ClientError as e:
            raise HTTPException(status_code=500, detail=f"{API_ERR_CONNECTION_ERROR}: {str(e)}")


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
    if IS_DEBUG:
        print(f"delete_event: credentials: {credentials}")
        
    user_info = authenticate_with_nextcloud(credentials)
    if IS_DEBUG:
        print(f"delete_event: User info: {user_info}")
    
    caldav_url = gen_nxtcloud_url_calendar(user_info['id'], calendar_name)
    if IS_DEBUG:
        print(f"delete_event: caldav_url: {caldav_url}")
    
    auth_header = gen_basic_auth_header(credentials.username, credentials.password)
    # Validate the UID
    if not uid:
        raise ValueError("Event UID must be provided for deletion")
    
    # Ensure the URL ends with a slash
    base_url = caldav_url if caldav_url.endswith('/') else f"{caldav_url}/"
    
    # Construct the URL for the event
    event_filename = f"{uid}.ics"
    event_url = f"{base_url}{event_filename}"
    
    if IS_DEBUG:
        print(f"Deleting event at URL: {event_url}")
    
    # Optional: Check if the event exists
    existing_event = await get_event_by_uid(credentials, uid, calendar_name)
    if not existing_event:
        if IS_DEBUG:
            print(f"Event with UID {uid} not found, nothing to delete")
        return False
    
    # Create headers for the DELETE request
    headers = {
        "authorization": auth_header
    }
    
    # Send the DELETE request
    async with aiohttp.ClientSession() as session:
        try:
            async with session.delete(event_url, headers=headers) as response:
                status_code = response.status
                
                # If we get a response, try to read the body
                response_text = await response.text() if response.content else ""
                
                # If event not found, return False
                if status_code == 404:
                    if IS_DEBUG:
                        print(f"Event with UID {uid} not found on server")
                    return False
                
                # Handle error responses
                if status_code not in (200, 204):  # 200 OK or 204 No Content are success codes for deletion
                    handle_caldav_response_status(status_code, response_text)
                
                if IS_DEBUG:
                    print(f"Event deleted successfully with UID: {uid}")
                
                return True
                
        except aiohttp.ClientError as e:
            raise HTTPException(status_code=500, detail=f"{API_ERR_CONNECTION_ERROR}: {str(e)}")
