# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

from fastapi import APIRouter, HTTPException, Depends, Path, Query
from typing import List, Optional
from functools import wraps
from src.common import security
from fastapi.security import HTTPBasicCredentials
from src.common.sec import authenticate_with_nextcloud
from src.models.event import Event
from src.models.api_params import UidParam, EventsQueryParams
from src.nextcloud.events import get_event_by_uid, get_events_by_time_range, create_event, update_event, delete_event
from src import logger

# --- Router Definition ---
# We're using the get_user_settings dependency directly in each endpoint
# instead of applying a global dependency to all routes
router = APIRouter()


def endpoint_error_handler(operation: str):
    """Decorator to normalize error handling across event endpoints."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except ValueError as e:
                res_txt = f"ValueError: {str(e)}"
                logger.error(res_txt)
                raise HTTPException(status_code=400, detail=res_txt)
            except HTTPException:
                raise
            except Exception as e:
                res_txt = f"Could not {operation}: {str(e)}"
                logger.error(res_txt)
                raise HTTPException(status_code=503, detail=res_txt)
        return wrapper
    return decorator

@router.get(
    "/{uid}",
    operation_id="get_event_by_uid",
    response_model=Event,
    summary="Get event by UID",
    description="Retrieve a single event by its unique identifier",
    responses={
        200: {
            "description": "Event retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "uid": "550e8400-e29b-41d4-a716-446655440000",
                        "summary": "Team Sync",
                        "description": "Weekly planning touchpoint",
                        "location": "Conference Room A",
                        "url": "https://nextcloud.local/remote.php/dav/calendars/user/personal/550e8400-e29b-41d4-a716-446655440000.ics",
                        "start": "2025-04-21T14:00:00",
                        "end": "2025-04-21T15:00:00",
                        "all_day": False,
                        "status": "CONFIRMED",
                        "classification": "PRIVATE",
                        "organizer": "manager@example.com",
                        "attendees": [
                            {
                                "email": "manager@example.com",
                                "name": "Manager",
                                "role": "CHAIR",
                                "status": "ACCEPTED",
                                "type": "INDIVIDUAL"
                            }
                        ],
                        "reminders": [
                            {
                                "type": "DISPLAY",
                                "mode": "relative",
                                "offset": "-PT10M",
                                "relation": "START",
                                "fire_time": "2025-04-21T13:50:00",
                                "timezone": "Europe/Paris",
                                "description": "Reminder fires 10 minutes before start"
                            }
                        ]
                    }
                }
            },
        },
        400: {
            "description": "Invalid UID format",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid UID format provided"}
                }
            },
        },
        401: {
            "description": "Authentication failed",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid credentials"}
                }
            },
        },
        403: {
            "description": "Authorization refused",
            "content": {
                "application/json": {
                    "example": {"detail": "Access denied to calendar"}
                }
            },
        },
        404: {
            "description": "Event not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Event with UID 550e8400-e29b-41d4-a716-446655440000 not found"}
                }
            },
        },
        503: {
            "description": "Server error or connection issue",
            "content": {
                "application/json": {
                    "example": {"detail": "Could not retrieve event: Connection failed"}
                }
            },
        },
    },
    tags=["events"],
)
@endpoint_error_handler("retrieve event")
async def read_event_endpoint(
    uid: str = Path(
        ...,
        description="Unique identifier for the event",
        example="550e8400-e29b-41d4-a716-446655440000",
        min_length=1,
        max_length=255,
    ),
    privacy: bool = Query(
        False,
        description="Enable privacy mode to mask sensitive values in the response",
        example=False
    ),
    calendar_name: Optional[str] = Query(
        None,
        description="Optional calendar name to filter events from a specific calendar",
        example="personal",
        max_length=100
    ),
    credentials: HTTPBasicCredentials = Depends(security)
):
    """
    Retrieve a single event by its UID from the Nextcloud CalDAV calendar.
    
    Performs a CalDAV GET request to fetch a specific event using its unique identifier.
    The event data is retrieved from the Nextcloud server and converted from iCalendar format
    to a structured Event object.
    
    **Key Features:**
    - Direct event retrieval by UID
    - Complete event information including all fields
    - CalDAV protocol compliance
    - Efficient single-event lookup
    - Optional privacy mode for sensitive data masking
    - Optional calendar-specific filtering
    
    **Authentication:**
    Requires HTTP Basic Authentication with valid Nextcloud credentials.
    
    **UID Requirements:**
    - Must be a non-empty string
    - Should be a valid UUID or unique identifier
    - Case-sensitive matching
    - Maximum length of 255 characters
    
    **Privacy Parameter:**
    - **privacy**: Optional boolean parameter (default: False)
    - When set to True, masks or hides sensitive values in the response
    - Useful for protecting confidential information in logs or public displays
    
    **Calendar Filtering:**
    - **calendar_name**: Optional parameter to filter events from a specific calendar
    - If not provided, searches in the default "personal" calendar
    - Case-sensitive calendar name matching
    
    **Returned Data:**
    Complete event information including:
    - **Basic Details**: Summary, description, location, status
    - **Timing**: Start/end times, all-day flag, timezone information
    - **Participants**: Attendees with roles and participation status
    - **Organization**: Categories, organizer information
    - **Notifications**: Reminders and alarms
    - **Recurrence**: Recurring event patterns and exceptions
    - **Privacy**: `classification` field mirroring the CalDAV CLASS value (PUBLIC/PRIVATE/CONFIDENTIAL)
    - **Metadata**: Creation/modification timestamps, server URL
    
    **Reminder Payload:**
    Each reminder object includes a `mode` field (`absolute` or `relative`). Relative
    reminders provide their ISO 8601 duration in `offset`, the reference point in
    `relation` (START or END), and a computed `fire_time` convenience timestamp that
    reflects the event's timezone. Absolute reminders define `fire_time` alongside a
    `timezone` field, ensuring the API preserves the original TZID information from
    Nextcloud.
    
    **Note:** When privacy mode is enabled, certain sensitive fields may be masked
    or omitted from the response to protect confidential information.
    """
    logger.debug(f"Retrieving event with UID: {uid} with privacy mode: {privacy}")
    
    # Authenticate with Nextcloud
    user_info = authenticate_with_nextcloud(credentials)
    logger.debug(f"User credentials: {user_info}")
    
    # Pass privacy flag down so helper can mask sensitive fields when requested
    event = await get_event_by_uid(
        credentials=credentials,
        uid=uid,
        calendar_name=calendar_name,
        privacy = privacy,
    )
    
    # If event is not found, raise a 404 error
    if event is None:
        res_txt = f"Event with UID {uid} not found"
        logger.error(res_txt)
        raise HTTPException(status_code=404, detail=res_txt)
    
    return event


@router.get(
    "/",
    operation_id="get_events_by_timerange",
    response_model=List[Event],
    summary="Get events by time range",
    description="Retrieve events within a specified date/time range",
    responses={
        200: {
            "description": "Events retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "uid": "550e8400-e29b-41d4-a716-446655440000",
                            "summary": "Team Sync",
                            "start": "2025-04-21T14:00:00",
                            "end": "2025-04-21T15:00:00",
                            "classification": "PRIVATE"
                        },
                        {
                            "uid": "8c51dfa0-53a5-42fb-8f7c-90ce31c1f7f2",
                            "summary": "All Hands",
                            "start": "2025-04-22T09:00:00",
                            "end": "2025-04-22T10:00:00",
                            "classification": "PUBLIC"
                        }
                    ]
                }
            },
        },
        400: {
            "description": "Invalid datetime parameters",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_format": {
                            "summary": "Invalid datetime format",
                            "value": {"detail": "Invalid datetime format: 2025-13-01. Expected ISO format (YYYY-MM-DDTHH:MM:SS)"}
                        },
                        "invalid_range": {
                            "summary": "Invalid time range",
                            "value": {"detail": "end_datetime must be after start_datetime"}
                        }
                    }
                }
            },
        },
        401: {
            "description": "Authentication failed",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid credentials"}
                }
            },
        },
        403: {
            "description": "Authorization refused",
            "content": {
                "application/json": {
                    "example": {"detail": "Access denied to calendar"}
                }
            },
        },
        503: {
            "description": "Server error or connection issue",
            "content": {
                "application/json": {
                    "example": {"detail": "Could not retrieve events: Connection failed"}
                }
            },
        },
    },
    tags=["events"],
)
@endpoint_error_handler("retrieve events")
async def read_events_by_time_range_endpoint(
    start_datetime: str = Query(
        ...,
        description="Start datetime in ISO format (YYYY-MM-DDTHH:MM:SS)",
        example="2025-04-21T00:00:00",
        regex=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$"
    ),
    end_datetime: str = Query(
        ...,
        description="End datetime in ISO format (YYYY-MM-DDTHH:MM:SS)",
        example="2025-04-28T23:59:59",
        regex=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$"
    ),
    privacy: bool = Query(
        False,
        description="Enable privacy mode to mask sensitive values in the response",
        example=False
    ),
    calendar_name: Optional[str] = Query(
        None,
        description="Optional calendar name to filter events from a specific calendar",
        example="personal",
        max_length=100
    ),
    credentials: HTTPBasicCredentials = Depends(security)
):
    """
    Retrieve events within a specified date/time range from the Nextcloud CalDAV calendar.
    
    Performs a CalDAV REPORT request with calendar-query filtering to efficiently retrieve
    events that fall within the specified time range. All filtering is done server-side
    for optimal performance.
    
    **Key Features:**
    - Server-side time range filtering
    - Optional calendar-specific filtering
    - Chronological sorting by start time
    - CalDAV protocol compliance
    - Efficient bulk event retrieval
    - Optional privacy mode for sensitive data masking
    
    **Authentication:**
    Requires HTTP Basic Authentication with valid Nextcloud credentials.
    
    **Time Range Parameters:**
    - **start_datetime**: Beginning of the time range (inclusive)
    - **end_datetime**: End of the time range (inclusive)
    - Both must be in ISO format: YYYY-MM-DDTHH:MM:SS
    - End datetime must be after start datetime
    
    **Privacy Parameter:**
    - **privacy**: Optional boolean parameter (default: False)
    - When set to True, masks or hides sensitive values in the response
    - Useful for protecting confidential information in logs or public displays
    
    **Calendar Filtering:**
    - **calendar_name**: Optional parameter to filter events from a specific calendar
    - If not provided, searches across all accessible calendars
    - Case-sensitive calendar name matching
    
    **Result Ordering:**
    Events are returned sorted by their start datetime in ascending order,
    making it easy to display chronological event lists.
    
    **Performance Considerations:**
    - Larger time ranges may return more data and take longer to process
    - Consider using smaller time windows for better performance
    - Server-side filtering reduces network overhead compared to client-side filtering
    
    **Use Cases:**
    - Calendar view implementations (day, week, month views)
    - Event scheduling and conflict detection
    - Reporting and analytics on time-based event data
    - Integration with external calendar applications
    
    **Returned Data:**
    Each event in the response includes:
    - **Basic Details**: Summary, description, location, status
    - **Timing**: Start/end times, all-day flag, timezone information
    - **Participants**: Attendees with roles and participation status
    - **Organization**: Categories, organizer information
    - **Notifications**: Reminders and alarms
    - **Recurrence**: Recurring event patterns and exceptions
    - **Privacy**: `classification` value mirroring CalDAV CLASS (PUBLIC/PRIVATE/CONFIDENTIAL)
    - **Metadata**: Creation/modification timestamps, server URL
    
    **Reminder Payload:**
    Reminders include a `mode`, `offset` (when relative), `relation` (START/END), a
    convenience `fire_time`, and a `timezone` field for absolute alarms so clients can
    keep the precise TZID that Nextcloud stores in the ICS data.
    
    **Note:** When privacy mode is enabled, certain sensitive fields may be masked
    or omitted from the response to protect confidential information.
    """
    logger.debug(f"Retrieving events between {start_datetime} and {end_datetime} with privacy mode: {privacy}")
    
    # Authenticate with Nextcloud
    user_info = authenticate_with_nextcloud(credentials)
    logger.debug(f"User credentials: {user_info}")
    
    # CalDAV helper handles filtering plus optional privacy masking
    events = await get_events_by_time_range(
        calendar_name=calendar_name,
        credentials=credentials,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        privacy=privacy
    )
    
    return events


@router.post(
    "/",
    operation_id="create_event",
    response_model=Event,
    status_code=201,
    summary="Create a new event",
    description="Create a new event in the Nextcloud CalDAV calendar",
    responses={
        201: {
            "description": "Event created successfully",
            "model": Event,
        },
        400: {
            "description": "Invalid event data",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_datetime": {
                            "summary": "Invalid datetime format",
                            "value": {"detail": "Invalid datetime format in start field"}
                        },
                        "missing_required": {
                            "summary": "Missing required fields",
                            "value": {"detail": "Event summary and start time are required"}
                        },
                        "invalid_range": {
                            "summary": "Invalid time range",
                            "value": {"detail": "Event end time must be after start time"}
                        }
                    }
                }
            },
        },
        401: {
            "description": "Authentication failed",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid credentials"}
                }
            },
        },
        403: {
            "description": "Authorization refused",
            "content": {
                "application/json": {
                    "example": {"detail": "Access denied to calendar"}
                }
            },
        },
        503: {
            "description": "Server error or connection issue",
            "content": {
                "application/json": {
                    "example": {"detail": "Could not create event: Connection failed"}
                }
            },
        },
    },
    tags=["events"],
)
@endpoint_error_handler("create event")
async def create_event_endpoint(
    event: Event,
    calendar_name: Optional[str] = Query(
        None,
        description="Optional calendar name to create the event in a specific calendar",
        example="personal",
        max_length=100
    ),
    credentials: HTTPBasicCredentials = Depends(security)
):
    """
    Create a new event in the Nextcloud CalDAV calendar.
    
    Creates a new calendar event using the CalDAV protocol. The event data is converted
    to iCalendar format and stored in the specified Nextcloud calendar.
    
    **Key Features:**
    - Automatic UID generation if not provided
    - Full iCalendar format support
    - CalDAV protocol compliance
    - Comprehensive event information storage
    - Attendee management and invitation support
    - Optional calendar-specific creation
    
    **Authentication:**
    Requires HTTP Basic Authentication with valid Nextcloud credentials.
    
    **Calendar Selection:**
    - **calendar_name**: Optional parameter to create the event in a specific calendar
    - If not provided, creates the event in the default "personal" calendar
    - Case-sensitive calendar name matching
    
    **Event Information Supported:**
    - **Basic Details**: Summary (required), description, location, status
    - **Timing**: Start time (required), end time, all-day events, timezone
    - **Participants**: Attendees with roles, participation status, and contact info
    - **Organization**: Categories, organizer information, priority
    - **Notifications**: Multiple reminders with relative offsets or absolute fire times
    - **Recurrence**: Recurring event patterns and exceptions

    **Reminder Definition:**
    - Use `mode="relative"` with `offset` (ISO 8601 duration) and `relation` to tie the reminder to START/END.
    - Use `mode="absolute"` with `fire_time` and optional `timezone` (IANA TZID) for fixed timestamps so the server can round-trip the original alarm TZ.
    
    **UID Handling:**
    If no UID is provided in the request, a UUID4 will be automatically generated.
    The UID must be unique within the calendar.
    
    **Datetime Format:**
    All datetime fields must be in ISO format (YYYY-MM-DDTHH:MM:SS).
    For all-day events, set the all_day flag to true.
    
    **Attendee Management:**
    - Attendees can have different roles (REQ-PARTICIPANT, OPT-PARTICIPANT, CHAIR)
    - Participation status is automatically set to NEEDS-ACTION for new invitations
    - Email notifications may be sent depending on server configuration
    
    **Server Integration:**
    - Event is immediately available in all synchronized calendar clients
    - Server-generated fields (created, last_modified, url) are populated automatically
    - Organizer field is set based on the authenticated user
    
    **Data Privacy:**
    Write operations always persist the full event payload. Privacy masking
    is only available on the read endpoints (`GET /events` and `GET /events/{uid}`).
    """
    logger.debug(f"Received event to create: {event}")
    
    # Authenticate with Nextcloud
    user_info = authenticate_with_nextcloud(credentials)
    logger.debug(f"User credentials: {user_info}")
    
    # Call the create_event function to create the event on the server
    # None calendar_name defaults to the authenticated user's primary calendar
    created_event = await create_event(
        credentials=credentials,
        event=event,
        calendar_name=calendar_name
    )
    
    return created_event


@router.put(
    "/{uid}",
    operation_id="update_event_by_uid",
    response_model=Event,
    summary="Update an existing event",
    description="Update an existing event in the Nextcloud CalDAV calendar",
    responses={
        200: {
            "description": "Event updated successfully",
            "model": Event,
        },
        400: {
            "description": "Invalid event data or UID mismatch",
            "content": {
                "application/json": {
                    "examples": {
                        "uid_mismatch": {
                            "summary": "UID mismatch between path and event data",
                            "value": {"detail": "UID mismatch: 550e8400-e29b-41d4-a716-446655440000 in path vs 123e4567-e89b-12d3-a456-426614174000 in event data"}
                        },
                        "invalid_datetime": {
                            "summary": "Invalid datetime format",
                            "value": {"detail": "Invalid datetime format in start field"}
                        },
                        "invalid_range": {
                            "summary": "Invalid time range",
                            "value": {"detail": "Event end time must be after start time"}
                        }
                    }
                }
            },
        },
        401: {
            "description": "Authentication failed",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid credentials"}
                }
            },
        },
        403: {
            "description": "Authorization refused",
            "content": {
                "application/json": {
                    "example": {"detail": "Access denied to calendar"}
                }
            },
        },
        404: {
            "description": "Event not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Event with UID 550e8400-e29b-41d4-a716-446655440000 not found"}
                }
            },
        },
        503: {
            "description": "Server error or connection issue",
            "content": {
                "application/json": {
                    "example": {"detail": "Could not update event: Connection failed"}
                }
            },
        },
    },
    tags=["events"],
)
@endpoint_error_handler("update event")
async def update_event_endpoint(
    event: Event,
    uid: str = Path(..., description="Unique identifier for the event", example="550e8400-e29b-41d4-a716-446655440000"),
    calendar_name: Optional[str] = Query(
        None,
        description="Optional calendar name to update the event in a specific calendar",
        example="personal",
        max_length=100
    ),
    credentials: HTTPBasicCredentials = Depends(security)
):
    """
    Update an existing event in the Nextcloud CalDAV calendar.
    
    This endpoint performs a CalDAV PUT request to update an existing event in the specified
    Nextcloud calendar. It converts the Event object to iCalendar format and sends it
    to the server. The event must have a valid UID that exists on the server.
    
    **Key Features:**
    - Complete event information update
    - UID validation and consistency checking
    - CalDAV protocol compliance
    - Atomic update operations
    - Preserves event history and metadata
    - Optional calendar-specific updates
    
    **Authentication:**
    Requires HTTP Basic Authentication with valid Nextcloud credentials.
    
    **Request Structure:**
    - **Event Data**: Provided in the request body as a JSON object
    - **UID Parameter**: Specified in the URL path
    - **UID Consistency**: The UID in the path must match the UID in the event data
    
    **Calendar Selection:**
    - **calendar_name**: Optional parameter to update the event in a specific calendar
    - If not provided, updates the event in the default "personal" calendar
    - Case-sensitive calendar name matching
    
    **Update Behavior:**
    - All event fields can be updated except the UID
    - Server-generated fields (last_modified, url) are automatically updated
    - Attendee notifications may be sent depending on server configuration
    - Changes are immediately synchronized to all connected calendar clients
    
    **UID Handling:**
    If the event data doesn't include a UID, it will be automatically set from the path parameter.
    If both are provided, they must match exactly.
    
    **Data Privacy:**
    Privacy masking is not applied to update operations. Use the read endpoints
    when you need sanitized data for public surfaces.
    """
    logger.debug(f"Updating event with UID: {uid}")
    
    # Ensure the UID in the path matches the UID in the event data
    if event.uid and event.uid != uid:
        res_txt = f"UID in path ({uid}) doesn't match event UID ({event.uid})"
        logger.error(res_txt)
        raise HTTPException(
            status_code=400,
            detail=res_txt
        )
    logger.debug(f"Updating event with UID: {uid}")
    
    # Authenticate with Nextcloud
    user_info = authenticate_with_nextcloud(credentials)
    logger.debug(f"User credentials: {user_info}")
    
    # Set the UID from the path if not provided in the event data
    if not event.uid:
        event.uid = uid
    
    # Call the update_event function to update the event on the server
    # calendar_name falling back to None keeps behavior aligned with Nextcloud defaults
    updated_event = await update_event(
        credentials=credentials,
        event=event,
        calendar_name=calendar_name
    )
    
    return updated_event


@router.delete(
    "/{uid}",
    operation_id="delete_event_by_uid",
    status_code=204,
    summary="Delete an event",
    description="Delete an event from the Nextcloud CalDAV calendar",
    responses={
        204: {
            "description": "Event deleted successfully",
        },
        400: {
            "description": "Invalid UID format",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid UID format provided"}
                }
            },
        },
        401: {
            "description": "Authentication failed",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid credentials"}
                }
            },
        },
        403: {
            "description": "Authorization refused",
            "content": {
                "application/json": {
                    "example": {"detail": "Access denied to calendar"}
                }
            },
        },
        404: {
            "description": "Event not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Event with UID 550e8400-e29b-41d4-a716-446655440000 not found"}
                }
            },
        },
        503: {
            "description": "Server error or connection issue",
            "content": {
                "application/json": {
                    "example": {"detail": "Could not delete event: Connection failed"}
                }
            },
        },
    },
    tags=["events"],
)
@endpoint_error_handler("delete event")
async def delete_event_endpoint(
    uid: str = Path(..., description="Unique identifier for the event", example="550e8400-e29b-41d4-a716-446655440000"),
    calendar_name: Optional[str] = Query(
        None,
        description="Optional calendar name to delete the event from a specific calendar",
        example="personal",
        max_length=100
    ),
    credentials: HTTPBasicCredentials = Depends(security)
):
    """
    Delete an event from the Nextcloud CalDAV calendar.
    
    This endpoint performs a CalDAV DELETE request to remove an event from the specified
    Nextcloud calendar. It requires the UID of the event to delete.
    
    **Key Features:**
    - Permanent event removal
    - CalDAV protocol compliance
    - Atomic delete operations
    - Immediate synchronization across clients
    - Cascade deletion of related data
    - Optional calendar-specific deletion
    
    **Authentication:**
    Requires HTTP Basic Authentication with valid Nextcloud credentials.
    
    **UID Parameter:**
    - **uid**: Unique identifier of the event to delete
    - Must be a valid, existing event UID
    - Case-sensitive matching
    - Maximum length of 255 characters
    
    **Calendar Selection:**
    - **calendar_name**: Optional parameter to delete the event from a specific calendar
    - If not provided, deletes the event from the default "personal" calendar
    - Case-sensitive calendar name matching
    
    **Deletion Behavior:**
    - Event is permanently removed from the calendar
    - All associated data (attendees, reminders, etc.) is also deleted
    - Changes are immediately synchronized to all connected calendar clients
    - Deletion cannot be undone through the API
    
    **Data Privacy:**
    Privacy masking only affects read endpoints. Delete operations never return
    event data beyond success/failure metadata.
    """
    logger.debug(f"Deleting event with UID: {uid}")
    
    # Authenticate with Nextcloud
    user_info = authenticate_with_nextcloud(credentials)
    logger.debug(f"User credentials: {user_info}")
    
    # Call the delete_event function to delete the event from the server
    # calendar_name None indicates the default "personal" calendar on Nextcloud
    result = await delete_event(
        credentials=credentials,
        uid=uid,
        calendar_name=calendar_name
    )
    
    # If the event was not found, return a 404 error
    if not result:
        res_txt = f"Event with UID {uid} not found"
        logger.error(res_txt)
        raise HTTPException(status_code=404, detail=res_txt)
    
    # Return 204 No Content on successful deletion
    return None
