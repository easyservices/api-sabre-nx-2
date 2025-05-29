# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

from fastapi import APIRouter, HTTPException, Depends, Path, Query
from typing import List, Optional
from src.common import security
from fastapi.security import HTTPBasicCredentials
from src.common.sec import authenticate_with_nextcloud
from src.models.event import Event
from src.models.api_params import UidParam, EventsQueryParams
from src.nextcloud.events import get_event_by_uid, get_events_by_time_range, create_event, update_event, delete_event

IS_DEBUG = True

# --- Router Definition ---
# We're using the get_user_settings dependency directly in each endpoint
# instead of applying a global dependency to all routes
router = APIRouter()

@router.get(
    "/{uid}",
    operation_id="get_event_by_uid",
    response_model=Event,
    summary="Get event by UID",
    description="Retrieve a single event by its unique identifier",
    responses={
        200: {
            "description": "Event retrieved successfully",
            "model": Event,
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
async def read_event_endpoint(
    uid: str = Path(
        ...,
        description="Unique identifier for the event",
        example="550e8400-e29b-41d4-a716-446655440000",
        min_length=1,
        max_length=255,
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
    
    **Authentication:**
    Requires HTTP Basic Authentication with valid Nextcloud credentials.
    
    **UID Requirements:**
    - Must be a non-empty string
    - Should be a valid UUID or unique identifier
    - Case-sensitive matching
    - Maximum length of 255 characters
    
    **Returned Data:**
    Complete event information including:
    - **Basic Details**: Summary, description, location, status
    - **Timing**: Start/end times, all-day flag, timezone information
    - **Participants**: Attendees with roles and participation status
    - **Organization**: Categories, organizer information
    - **Notifications**: Reminders and alarms
    - **Recurrence**: Recurring event patterns and exceptions
    - **Metadata**: Creation/modification timestamps, server URL
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


@router.get(
    "/",
    operation_id="get_events_by_timerange",
    response_model=List[Event],
    summary="Get events by time range",
    description="Retrieve events within a specified date/time range",
    responses={
        200: {
            "description": "Events retrieved successfully",
            "model": List[Event],
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
    
    **Authentication:**
    Requires HTTP Basic Authentication with valid Nextcloud credentials.
    
    **Time Range Parameters:**
    - **start_datetime**: Beginning of the time range (inclusive)
    - **end_datetime**: End of the time range (inclusive)
    - Both must be in ISO format: YYYY-MM-DDTHH:MM:SS
    - End datetime must be after start datetime
    
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
    """
    try:
        if IS_DEBUG:
            print(f"Retrieving events between {start_datetime} and {end_datetime}")
        
        # Authenticate with Nextcloud
        user_info = authenticate_with_nextcloud(credentials)
        if IS_DEBUG:
            print(f"read_events_by_time_range_endpoint: user_info: {user_info.get('id', 'not authenticated')}")
        
        # Call the get_events_by_time_range function to retrieve events from the server
        events = await get_events_by_time_range(
            calendar_name=calendar_name,
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
async def create_event_endpoint(
    event: Event,
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
    
    **Authentication:**
    Requires HTTP Basic Authentication with valid Nextcloud credentials.
    
    **Event Information Supported:**
    - **Basic Details**: Summary (required), description, location, status
    - **Timing**: Start time (required), end time, all-day events, timezone
    - **Participants**: Attendees with roles, participation status, and contact info
    - **Organization**: Categories, organizer information, priority
    - **Notifications**: Multiple reminders with different trigger times and types
    - **Recurrence**: Recurring event patterns and exceptions
    
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
async def update_event_endpoint(
    event: Event,
    uid: str = Path(..., description="Unique identifier for the event", example="550e8400-e29b-41d4-a716-446655440000"),
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
    
    **Authentication:**
    Requires HTTP Basic Authentication with valid Nextcloud credentials.
    
    **Request Structure:**
    - **Event Data**: Provided in the request body as a JSON object
    - **UID Parameter**: Specified in the URL path
    - **UID Consistency**: The UID in the path must match the UID in the event data
    
    **Update Behavior:**
    - All event fields can be updated except the UID
    - Server-generated fields (last_modified, url) are automatically updated
    - Attendee notifications may be sent depending on server configuration
    - Changes are immediately synchronized to all connected calendar clients
    
    **UID Handling:**
    If the event data doesn't include a UID, it will be automatically set from the path parameter.
    If both are provided, they must match exactly.
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
async def delete_event_endpoint(
    uid: str = Path(..., description="Unique identifier for the event", example="550e8400-e29b-41d4-a716-446655440000"),
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
    
    **Authentication:**
    Requires HTTP Basic Authentication with valid Nextcloud credentials.
    
    **UID Parameter:**
    - **uid**: Unique identifier of the event to delete
    - Must be a valid, existing event UID
    - Case-sensitive matching
    - Maximum length of 255 characters
    
    **Deletion Behavior:**
    - Event is permanently removed from the calendar
    - All associated data (attendees, reminders, etc.) is also deleted
    - Changes are immediately synchronized to all connected calendar clients
    - Deletion cannot be undone through the API
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