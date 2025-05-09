# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

from fastapi import APIRouter, HTTPException, Depends
from typing import List
from src.common import security
from fastapi.security import HTTPBasicCredentials
from src.common.sec import authenticate_with_nextcloud
from src.models.event import Event
from src.nextcloud.events import get_event_by_uid, get_events_by_time_range, create_event, update_event, delete_event

IS_DEBUG = False

# --- Router Definition ---
# We're using the get_user_settings dependency directly in each endpoint
# instead of applying a global dependency to all routes
router = APIRouter()

# --- Endpoints ---
# Each endpoint uses the get_user_settings dependency to get the user settings
# directly from the API key provided in the X-API-Key header

@router.get("/{uid}", operation_id="get_event_by_uid", response_model=Event)
async def read_event_endpoint(
    uid: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    """
    Retrieve a single event by its UID from the Nextcloud CalDAV calendar.
    
    This endpoint performs a CalDAV GET request to retrieve a specific event by its UID
    from the specified Nextcloud calendar. It requires HTTP Basic Authentication with
    Nextcloud credentials.
    
    The event is identified by its UID, which must be provided in the URL path.
    
    Authentication:
        HTTP Basic Authentication with Nextcloud credentials
    
    Returns:
        Event: The Event object if found
    
    Raises:
        HTTPException(401): If authentication fails
        HTTPException(403): If authorization is refused
        HTTPException(404): If the event is not found
        HTTPException(503): If there's a server error or connection issue
    
    Example Request:
        GET /events/550e8400-e29b-41d4-a716-446655440000
        Headers:
            Authorization: Basic dXNlcm5hbWU6cGFzc3dvcmQ=
            
    Example Response:
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
    """
    try:
        if IS_DEBUG:
            print(f"Retrieving event with UID: {uid}")
        
        # Authenticate with Nextcloud
        user_info = authenticate_with_nextcloud(credentials)
        if IS_DEBUG:
            print(f"read_event_endpoint: user_info: {user_info}")
        
        # Call the get_event_by_uid function to retrieve the event from the server
        event = await get_event_by_uid(
            credentials=credentials,
            uid=uid
        )
        
        # If event is not found, raise a 404 error
        if event is None:
            raise HTTPException(status_code=404, detail=f"Event with UID {uid} not found")
        
        return event
        
    except ValueError as e:
        # Handle validation errors
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if IS_DEBUG:
            print(f"Error retrieving event: {e}")
        raise HTTPException(status_code=503, detail=f"Could not retrieve event: {str(e)}")


@router.get("/", operation_id="get_event_by_timerange", response_model=List[Event])
async def read_events_by_time_range_endpoint(
    start_datetime: str,
    end_datetime: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    """
    Retrieve events between a start and end date/time from the Nextcloud CalDAV calendar.
    
    This endpoint performs a CalDAV REPORT request with a calendar-query to retrieve events
    that fall within the specified time range. The filtering is done server-side for efficiency.
    It requires HTTP Basic Authentication with Nextcloud credentials.
    
    The events are returned sorted by their start datetime.
    
    Query Parameters:
        start_datetime: Start datetime in ISO format (YYYY-MM-DDTHH:MM:SS)
        end_datetime: End datetime in ISO format (YYYY-MM-DDTHH:MM:SS)
    
    Authentication:
        HTTP Basic Authentication with Nextcloud credentials
    
    Returns:
        List[Event]: A list of Event objects within the specified time range, sorted by start datetime
    
    Raises:
        HTTPException(400): If the datetime parameters are invalid
        HTTPException(401): If authentication fails
        HTTPException(403): If authorization is refused
        HTTPException(503): If there's a server error or connection issue
    
    Example Request:
        GET /events/?start_datetime=2025-04-21T00:00:00&end_datetime=2025-04-28T23:59:59
        Headers:
            Authorization: Basic dXNlcm5hbWU6cGFzc3dvcmQ=
            
    Example Response:
        [
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
          },
          {
            "uid": "550e8400-e29b-41d4-a716-446655440001",
            "summary": "Project Review",
            "description": "Monthly project status review",
            "location": "Conference Room B",
            "url": "https://nextcloud.example.com/remote.php/dav/calendars/username/personal/550e8400-e29b-41d4-a716-446655440001.ics",
            "start": "2025-04-22T10:00:00",
            "end": "2025-04-22T11:30:00",
            "all_day": false,
            "created": "2025-04-01T10:00:00",
            "last_modified": "2025-04-01T10:00:00",
            "status": "CONFIRMED",
            "organizer": "manager@example.com",
            "categories": ["MEETING", "PROJECT"],
            "attendees": [
              {
                "email": "john.doe@example.com",
                "name": "John Doe",
                "role": "REQ-PARTICIPANT",
                "status": "ACCEPTED",
                "type": "INDIVIDUAL"
              },
              {
                "email": "jane.smith@example.com",
                "name": "Jane Smith",
                "role": "REQ-PARTICIPANT",
                "status": "TENTATIVE",
                "type": "INDIVIDUAL"
              }
            ],
            "reminders": [
              {
                "type": "DISPLAY",
                "trigger": "-PT30M",
                "description": "Reminder: Project Review"
              }
            ],
            "recurrence": "FREQ=MONTHLY;BYMONTHDAY=22",
            "recurrence_id": null
          }
        ]
    """
    try:
        if IS_DEBUG:
            print(f"Retrieving events between {start_datetime} and {end_datetime}")
        
        # Authenticate with Nextcloud
        user_info = authenticate_with_nextcloud(credentials)
        if IS_DEBUG:
            print(f"read_events_by_time_range_endpoint: user_info: {user_info}")
        
        # Call the get_events_by_time_range function to retrieve events from the server
        events = await get_events_by_time_range(
            credentials=credentials,
            start_datetime=start_datetime,
            end_datetime=end_datetime
        )
        
        if IS_DEBUG:
            print(f"Retrieved {len(events)} events")
        
        return events
        
    except ValueError as e:
        # Handle validation errors (e.g., invalid datetime format)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if IS_DEBUG:
            print(f"Error retrieving events: {e}")
        raise HTTPException(status_code=503, detail=f"Could not retrieve events: {str(e)}")


@router.post("/", operation_id="create_event", response_model=Event)
async def create_event_endpoint(
    event: Event,
    credentials: HTTPBasicCredentials = Depends(security)
):
    """
    Create a new event in the Nextcloud CalDAV calendar.
    
    This endpoint performs a CalDAV PUT request to create a new event in the specified
    Nextcloud calendar. It converts the Event object to iCalendar format and sends it
    to the server.
    
    The event data is provided in the request body as a JSON object.
    
    Authentication:
        HTTP Basic Authentication with Nextcloud credentials
    
    Returns:
        Event: The created Event object with updated information from the server
    
    Raises:
        HTTPException(400): If the event data is invalid
        HTTPException(401): If authentication fails
        HTTPException(403): If authorization is refused
        HTTPException(503): If there's a server error or connection issue
    
    Example Request:
        POST /events/
        Headers:
            Authorization: Basic dXNlcm5hbWU6cGFzc3dvcmQ=
            Content-Type: application/json
        Body:
            {
                "summary": "Team Meeting",
                "description": "Weekly team sync-up",
                "location": "Conference Room A",
                "start": "2025-04-21T14:00:00",
                "end": "2025-04-21T15:00:00",
                "all_day": false,
                "status": "CONFIRMED",
                "categories": ["MEETING", "WORK"],
                "attendees": [
                    {
                        "email": "john.doe@example.com",
                        "name": "John Doe",
                        "role": "REQ-PARTICIPANT"
                    }
                ],
                "reminders": [
                    {
                        "type": "DISPLAY",
                        "trigger": "-PT15M",
                        "description": "Reminder: Team Meeting"
                    }
                ]
            }
            
    Example Response:
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
              "status": "NEEDS-ACTION",
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
          "recurrence": null,
          "recurrence_id": null
        }
    """
    try:
        if IS_DEBUG:
            print(f"Creating event with summary: {event.summary}")
        
        # Authenticate with Nextcloud
        user_info = authenticate_with_nextcloud(credentials)
        if IS_DEBUG:
            print(f"create_event_endpoint: user_info: {user_info}")
        
        # Call the create_event function to create the event on the server
        created_event = await create_event(
            credentials=credentials,
            event=event
        )
        
        if IS_DEBUG:
            print(f"Event created successfully with UID: {created_event.uid}")
        
        return created_event
        
    except ValueError as e:
        # Handle validation errors
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if IS_DEBUG:
            print(f"Error creating event: {e}")
        raise HTTPException(status_code=503, detail=f"Could not create event: {str(e)}")


@router.put("/{uid}", operation_id="update_event_by_uid", response_model=Event)
async def update_event_endpoint(
    uid: str,
    event: Event,
    credentials: HTTPBasicCredentials = Depends(security)
):
    """
    Update an existing event in the Nextcloud CalDAV calendar.
    
    This endpoint performs a CalDAV PUT request to update an existing event in the specified
    Nextcloud calendar. It converts the Event object to iCalendar format and sends it
    to the server. The event must have a valid UID that exists on the server.
    
    The event data is provided in the request body as a JSON object, and the UID is specified
    in the URL path. The UID in the path must match the UID in the event data.
    
    Authentication:
        HTTP Basic Authentication with Nextcloud credentials
    
    Returns:
        Event: The updated Event object with any additional information from the server
    
    Raises:
        HTTPException(400): If the event data is invalid or the UIDs don't match
        HTTPException(401): If authentication fails
        HTTPException(403): If authorization is refused
        HTTPException(404): If the event is not found
        HTTPException(503): If there's a server error or connection issue
    
    Example Request:
        PUT /events/550e8400-e29b-41d4-a716-446655440000
        Headers:
            Authorization: Basic dXNlcm5hbWU6cGFzc3dvcmQ=
            Content-Type: application/json
        Body:
            {
                "uid": "550e8400-e29b-41d4-a716-446655440000",
                "summary": "Updated Team Meeting",
                "description": "Weekly team sync-up with updated agenda",
                "location": "Conference Room B",
                "start": "2025-04-21T15:00:00",
                "end": "2025-04-21T16:00:00",
                "all_day": false,
                "status": "CONFIRMED",
                "categories": ["MEETING", "WORK", "UPDATED"],
                "attendees": [
                    {
                        "email": "john.doe@example.com",
                        "name": "John Doe",
                        "role": "REQ-PARTICIPANT"
                    },
                    {
                        "email": "jane.smith@example.com",
                        "name": "Jane Smith",
                        "role": "OPT-PARTICIPANT"
                    }
                ]
            }
            
    Example Response:
        {
          "uid": "550e8400-e29b-41d4-a716-446655440000",
          "summary": "Updated Team Meeting",
          "description": "Weekly team sync-up with updated agenda",
          "location": "Conference Room B",
          "url": "https://nextcloud.example.com/remote.php/dav/calendars/username/personal/550e8400-e29b-41d4-a716-446655440000.ics",
          "start": "2025-04-21T15:00:00",
          "end": "2025-04-21T16:00:00",
          "all_day": false,
          "created": "2025-04-01T10:00:00",
          "last_modified": "2025-04-01T11:00:00",
          "status": "CONFIRMED",
          "organizer": "organizer@example.com",
          "categories": ["MEETING", "WORK", "UPDATED"],
          "attendees": [
            {
              "email": "john.doe@example.com",
              "name": "John Doe",
              "role": "REQ-PARTICIPANT",
              "status": "NEEDS-ACTION",
              "type": "INDIVIDUAL"
            },
            {
              "email": "jane.smith@example.com",
              "name": "Jane Smith",
              "role": "OPT-PARTICIPANT",
              "status": "NEEDS-ACTION",
              "type": "INDIVIDUAL"
            }
          ],
          "reminders": [
            {
              "type": "DISPLAY",
              "trigger": "-PT15M",
              "description": "Reminder: Updated Team Meeting"
            }
          ],
          "recurrence": null,
          "recurrence_id": null
        }
    """
    try:
        if IS_DEBUG:
            print(f"Updating event with UID: {uid}")
        
        # Authenticate with Nextcloud
        user_info = authenticate_with_nextcloud(credentials)
        if IS_DEBUG:
            print(f"update_event_endpoint: user_info: {user_info}")
        
        # Ensure the UID in the path matches the UID in the event data
        if event.uid and event.uid != uid:
            raise ValueError(f"UID mismatch: {uid} in path vs {event.uid} in event data")
        
        # Set the UID from the path if not provided in the event data
        if not event.uid:
            event.uid = uid
        
        # Call the update_event function to update the event on the server
        updated_event = await update_event(
            credentials=credentials,
            event=event
        )
        
        if IS_DEBUG:
            print(f"Event updated successfully with UID: {updated_event.uid}")
        
        return updated_event
        
    except ValueError as e:
        # Handle validation errors
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if IS_DEBUG:
            print(f"Error updating event: {e}")
        raise HTTPException(status_code=503, detail=f"Could not update event: {str(e)}")


@router.delete("/{uid}", operation_id="delete_event_by_uid", status_code=204)
async def delete_event_endpoint(
    uid: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    """
    Delete an event from the Nextcloud CalDAV calendar.
    
    This endpoint performs a CalDAV DELETE request to remove an event from the specified
    Nextcloud calendar. It requires the UID of the event to delete.
    
    The event UID is specified in the URL path.
    
    Authentication:
        HTTP Basic Authentication with Nextcloud credentials
    
    Returns:
        204 No Content on successful deletion
    
    Raises:
        HTTPException(400): If the UID is invalid
        HTTPException(401): If authentication fails
        HTTPException(403): If authorization is refused
        HTTPException(404): If the event is not found
        HTTPException(503): If there's a server error or connection issue
    
    Example Request:
        DELETE /events/550e8400-e29b-41d4-a716-446655440000
        Headers:
            Authorization: Basic dXNlcm5hbWU6cGFzc3dvcmQ=
            
    Example Response:
        HTTP/1.1 204 No Content
    """
    try:
        if IS_DEBUG:
            print(f"Deleting event with UID: {uid}")
        
        # Authenticate with Nextcloud
        user_info = authenticate_with_nextcloud(credentials)
        if IS_DEBUG:
            print(f"delete_event_endpoint: user_info: {user_info}")
        
        # Call the delete_event function to delete the event from the server
        result = await delete_event(
            credentials=credentials,
            uid=uid
        )
        
        # If the event was not found, return a 404 error
        if not result:
            raise HTTPException(status_code=404, detail=f"Event with UID {uid} not found")
        
        if IS_DEBUG:
            print(f"Event deleted successfully with UID: {uid}")
        
        # Return 204 No Content on successful deletion
        return None
        
    except ValueError as e:
        # Handle validation errors
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if IS_DEBUG:
            print(f"Error deleting event: {e}")
        raise HTTPException(status_code=503, detail=f"Could not delete event: {str(e)}")