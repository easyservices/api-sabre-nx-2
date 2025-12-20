# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

from fastapi import APIRouter, HTTPException, Depends, Path, Query, Response
from time import perf_counter
from typing import List

from src.api.responses import EVENT_ERROR_RESPONSES
from src.common.cache import (
    build_cache_key,
    get_event_caches,
    invalidate_event_caches_for_user,
    set_cache_headers,
)
from src.common.nextcloud_utils import run_nextcloud_call
from src.common.validation import validate_time_range, validate_event_datetimes
from src.dependencies.auth import authenticated_user, AuthContext
from src.models.event import (
    Event,
    RecurrenceInstance,
    RecurrencePreviewRequest,
    RecurrenceRuleRequest,
    RecurrenceExceptionRequest,
    RecurrenceSkipRequest,
    RecurrencePreviewResponse,
)
from src.nextcloud.events import (
    get_event_by_uid,
    get_events_by_time_range,
    create_event,
    update_event,
    delete_event,
    list_calendars,
    expand_recurrence_instances,
    preview_recurrence,
    build_recurrence_rule,
    upsert_recurrence_exception,
    skip_recurrence_instances,
)
from src import logger


async def _ensure_calendar_exists(calendar_name: str, auth: AuthContext):
    """Validate that the requested calendar exists for the user."""
    calendars = await list_calendars(credentials=auth.credentials, user_info=auth.user_info)
    if not calendars:
        logger.error("No calendars available", extra={"user": auth.credentials.username})
        raise HTTPException(status_code=404, detail="No calendars available for user")
    target = calendar_name.lower()
    for cal in calendars:
        name = (cal.get("name") or "").lower()
        url = (cal.get("url") or "").lower()
        if target == name or target in url:
            return
    logger.error("Calendar not found", extra={"user": auth.credentials.username, "calendar": calendar_name})
    raise HTTPException(status_code=404, detail=f"Calendar '{calendar_name}' not found")

# --- Router Definition ---
# We're using the get_user_settings dependency directly in each endpoint
# instead of applying a global dependency to all routes
router = APIRouter()

@router.get(
    "/calendars",
    operation_id="list_calendars",
    summary="List calendars for the authenticated user",
    description=(
        "Discover all CalDAV calendars visible to the authenticated user. "
        "Each entry includes the calendar display name (when provided) and its CalDAV URL. "
        "Responses are cached briefly per user to avoid repeated principal discovery."
    ),
    tags=["events"],
    responses={
        200: {"description": "Calendars retrieved successfully"},
        **EVENT_ERROR_RESPONSES,
    },
)
async def list_calendars_endpoint(
    response: Response,
    auth: AuthContext = Depends(authenticated_user),
):
    """
    Return all calendars the authenticated user can access.

    - Requires HTTP Basic Auth.
    - Uses CalDAV principal discovery.
    - Caches results per user for a short period to speed up subsequent calls.
    """
    start_time = perf_counter()
    caches = get_event_caches()
    cache_key = build_cache_key(auth.credentials.username, "calendars")
    if cache_key in caches.calendars:
        set_cache_headers(response, caches.calendars, cache_key, hit=True)
        logger.debug("calendars cache hit", extra={"user": auth.credentials.username})
        return caches.calendars[cache_key]

    try:
        calendars = await run_nextcloud_call(
            "list calendars",
            list_calendars,
            credentials=auth.credentials,
            user_info=auth.user_info,
        )
        caches.calendars[cache_key] = calendars
        set_cache_headers(response, caches.calendars, cache_key, hit=False)
        return calendars
    finally:
        logger.debug(
            "calendars.done",
            extra={"user": auth.credentials.username, "elapsed_ms": int((perf_counter() - start_time) * 1000)},
        )

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
        **EVENT_ERROR_RESPONSES,
        404: {
            "description": "Event not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Event with UID 550e8400-e29b-41d4-a716-446655440000 not found"}
                }
            },
        },
    },
    tags=["events"],
)
async def read_event_endpoint(
    response: Response,
    uid: str = Path(
        ...,
        description="Unique identifier for the event",
        example="550e8400-e29b-41d4-a716-446655440000",
        min_length=3,
        max_length=255,
        regex=r"^[A-Za-z0-9._\\-]{3,255}$",
    ),
    auth: AuthContext = Depends(authenticated_user),
    privacy: bool = Query(
        False,
        description="Enable privacy mode to mask sensitive values in the response",
        example=False
    ),
    calendar_name: str = Query(
        "personal",
        description="Optional calendar name to filter events from a specific calendar",
        example="personal",
        max_length=100,
        min_length=1,
    ),
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
    - **Metadata**: Creation/modification timestamps, server URL
    
    **Note:** When privacy mode is enabled, certain sensitive fields may be masked
    or omitted from the response to protect confidential information.
    """
    start_time = perf_counter()
    try:
        logger.debug("event.get start", extra={"uid": uid, "calendar": calendar_name, "user": auth.credentials.username, "privacy": privacy})
        if not calendar_name.strip():
            raise HTTPException(status_code=400, detail="Calendar name must not be empty")
        await _ensure_calendar_exists(calendar_name, auth)

        caches = get_event_caches()
        cache_key = build_cache_key(auth.credentials.username, "event", uid, calendar_name, str(privacy))
        if cache_key in caches.by_uid:
            if response:
                set_cache_headers(response, caches.by_uid, cache_key, hit=True)
            return caches.by_uid[cache_key]

        event = await run_nextcloud_call(
            "retrieve event",
            get_event_by_uid,
            credentials=auth.credentials,
            uid=uid,
            calendar_name=calendar_name,
            privacy=privacy,
            user_info=auth.user_info,
        )
        
        if event is None:
            res_txt = f"Event with UID {uid} not found"
            logger.error(res_txt)
            raise HTTPException(status_code=404, detail=res_txt)

        caches.by_uid[cache_key] = event
        if response:
            set_cache_headers(response, caches.by_uid, cache_key, hit=False)
        return event
    finally:
        logger.debug(
            "event.get done",
            extra={"uid": uid, "calendar": calendar_name, "user": auth.credentials.username, "elapsed_ms": int((perf_counter() - start_time) * 1000)},
        )


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
        **EVENT_ERROR_RESPONSES,
    },
    tags=["events"],
)
async def read_events_by_time_range_endpoint(
    response: Response,
    auth: AuthContext = Depends(authenticated_user),
    start_datetime: str = Query(
        ...,
        description="Start datetime in ISO format (YYYY-MM-DDTHH:MM:SS)",
        example="2025-04-21T00:00:00",
        regex=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})?$"
    ),
    end_datetime: str = Query(
        ...,
        description="End datetime in ISO format (YYYY-MM-DDTHH:MM:SS)",
        example="2025-04-28T23:59:59",
        regex=r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:Z|[+-]\d{2}:\d{2})?$"
    ),
    privacy: bool = Query(
        False,
        description="Enable privacy mode to mask sensitive values in the response",
        example=False
    ),
    calendar_name: str = Query(
        "personal",
        description="Optional calendar name to filter events from a specific calendar",
        example="personal",
        max_length=100,
        min_length=1,
    ),
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
    
    **Note:** When privacy mode is enabled, certain sensitive fields may be masked
    or omitted from the response to protect confidential information.
    """
    start_time = perf_counter()
    try:
        logger.debug(
            "event.range start",
            extra={"user": auth.credentials.username, "calendar": calendar_name, "start": start_datetime, "end": end_datetime, "privacy": privacy},
        )
        if not calendar_name.strip():
            raise HTTPException(status_code=400, detail="Calendar name must not be empty")
        validate_time_range(start_datetime, end_datetime, label_prefix="Time range")
        await _ensure_calendar_exists(calendar_name, auth)
        caches = get_event_caches()
        cache_key = build_cache_key(auth.credentials.username, "events_range", start_datetime, end_datetime, calendar_name or "", str(privacy))
        if cache_key in caches.by_range:
            if response:
                set_cache_headers(response, caches.by_range, cache_key, hit=True)
            return caches.by_range[cache_key]

        events = await run_nextcloud_call(
            "retrieve events",
            get_events_by_time_range,
            calendar_name=calendar_name,
            credentials=auth.credentials,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            privacy=privacy,
            user_info=auth.user_info,
        )

        caches.by_range[cache_key] = events
        if response:
            set_cache_headers(response, caches.by_range, cache_key, hit=False)
        return events
    finally:
        logger.debug(
            "event.range done",
            extra={"user": auth.credentials.username, "calendar": calendar_name, "elapsed_ms": int((perf_counter() - start_time) * 1000)},
        )


@router.get(
    "/recurring/{uid}/instances",
    operation_id="get_recurring_instances",
    response_model=List[RecurrenceInstance],
    summary="Expand recurring event instances",
    description="Expand a recurring event into concrete occurrences between the provided start and end datetimes.",
    tags=["events"],
)
async def get_recurring_instances_endpoint(
    response: Response,
    uid: str = Path(
        ...,
        description="UID of the recurring event to expand",
        min_length=3,
        max_length=255,
        regex=r"^[A-Za-z0-9._\\-]{3,255}$",
    ),
    start_datetime: str = Query(
        ...,
        description="Start datetime in ISO format (YYYY-MM-DDTHH:MM:SS)",
        example="2025-04-21T00:00:00",
    ),
    end_datetime: str = Query(
        ...,
        description="End datetime in ISO format (YYYY-MM-DDTHH:MM:SS)",
        example="2025-04-28T23:59:59",
    ),
    calendar_name: str = Query(
        "personal",
        description="Calendar containing the recurring event",
        example="personal",
        max_length=100,
        min_length=1,
    ),
    privacy: bool = Query(
        False,
        description="Enable privacy mode to mask sensitive values in the response",
        example=False,
    ),
    auth: AuthContext = Depends(authenticated_user),
):
    """Expand recurring event instances within a window."""
    start_time = perf_counter()
    try:
        if not calendar_name.strip():
            raise HTTPException(status_code=400, detail="Calendar name must not be empty")
        validate_time_range(start_datetime, end_datetime, label_prefix="Time range")
        await _ensure_calendar_exists(calendar_name, auth)
        caches = get_event_caches()
        cache_key = build_cache_key(auth.credentials.username, "events_recurring", uid, start_datetime, end_datetime, calendar_name, str(privacy))
        if cache_key in caches.by_range:
            set_cache_headers(response, caches.by_range, cache_key, hit=True)
            return caches.by_range[cache_key]
        instances = await run_nextcloud_call(
            "expand recurring instances",
            expand_recurrence_instances,
            credentials=auth.credentials,
            uid=uid,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            calendar_name=calendar_name,
            privacy=privacy,
            user_info=auth.user_info,
        )
        caches.by_range[cache_key] = instances
        set_cache_headers(response, caches.by_range, cache_key, hit=False)
        return instances
    finally:
        logger.debug(
            "event.recurrence.instances done",
            extra={"uid": uid, "calendar": calendar_name, "user": auth.credentials.username, "elapsed_ms": int((perf_counter() - start_time) * 1000)},
        )


@router.post(
    "/recurring/preview",
    operation_id="preview_recurrence_rule",
    response_model=RecurrencePreviewResponse,
    summary="Preview recurrence rule",
    description="Generate an RRULE and preview occurrences using either a raw RRULE string or a friendly recurrence payload.",
    tags=["events"],
)
async def preview_recurrence_endpoint(
    payload: RecurrencePreviewRequest,
    auth: AuthContext = Depends(authenticated_user),
):
    """Build and preview recurrence occurrences."""
    preview = preview_recurrence(
        start=payload.start,
        end=payload.end,
        all_day=payload.all_day,
        friendly=payload.friendly,
        rrule=payload.rrule,
        max_occurrences=payload.max_occurrences,
    )
    return RecurrencePreviewResponse(**preview)


@router.post(
    "/recurring/rule",
    operation_id="build_recurrence_rule",
    summary="Build recurrence rule from friendly fields",
    description="Generate an RRULE string and short summary from a friendly recurrence payload.",
    tags=["events"],
)
async def build_recurrence_rule_endpoint(
    payload: RecurrenceRuleRequest,
    auth: AuthContext = Depends(authenticated_user),
):
    """Build an RRULE string from a friendly payload."""
    return build_recurrence_rule(payload.friendly)


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
        **EVENT_ERROR_RESPONSES,
    },
    tags=["events"],
)
async def create_event_endpoint(
    event: Event,
    calendar_name: str = Query(
        "personal",
        description="Optional calendar name to create the event in a specific calendar",
        example="personal",
        max_length=100,
        min_length=1,
    ),
    auth: AuthContext = Depends(authenticated_user)
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
    
    **Note:** When privacy mode is enabled, certain sensitive fields may be masked
    or omitted from the response to protect confidential information.
    """
    start_time = perf_counter()
    try:
        if not calendar_name.strip():
            raise HTTPException(status_code=400, detail="Calendar name must not be empty")
        if event.categories:
            for cat in event.categories:
                if len(cat or "") > 64:
                    raise HTTPException(status_code=400, detail="Category values must be <=64 characters")
        validate_event_datetimes(event.start, event.end)

        logger.debug(
            "event.create start",
            extra={"user": auth.credentials.username, "calendar": calendar_name, "uid": event.uid},
        )
        await _ensure_calendar_exists(calendar_name, auth)
        
        created_event = await run_nextcloud_call(
            "create event",
            create_event,
            credentials=auth.credentials,
            event=event,
            calendar_name=calendar_name,
            user_info=auth.user_info,
        )
        
        invalidate_event_caches_for_user(auth.credentials.username)
        return created_event
    finally:
        logger.debug(
            "event.create done",
            extra={"user": auth.credentials.username, "calendar": calendar_name, "uid": event.uid, "elapsed_ms": int((perf_counter() - start_time) * 1000)},
        )


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
        **EVENT_ERROR_RESPONSES,
        404: {
            "description": "Event not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Event with UID 550e8400-e29b-41d4-a716-446655440000 not found"}
                }
            },
        },
    },
    tags=["events"],
)
async def update_event_endpoint(
    event: Event,
    uid: str = Path(
        ...,
        description="Unique identifier for the event",
        example="550e8400-e29b-41d4-a716-446655440000",
        min_length=3,
        max_length=255,
        regex=r"^[A-Za-z0-9._\\-]{3,255}$",
    ),
    calendar_name: str = Query(
        "personal",
        description="Optional calendar name to update the event in a specific calendar",
        example="personal",
        max_length=100,
        min_length=1,
    ),
    auth: AuthContext = Depends(authenticated_user)
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
    - Optional privacy mode for sensitive data masking
    
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
    
    **Note:** When privacy mode is enabled, certain sensitive fields may be masked
    or omitted from the response to protect confidential information.
    """
    start_time = perf_counter()
    try:
        if not calendar_name.strip():
            raise HTTPException(status_code=400, detail="Calendar name must not be empty")
        if event.categories:
            for cat in event.categories:
                if len(cat or "") > 64:
                    raise HTTPException(status_code=400, detail="Category values must be <=64 characters")
        validate_event_datetimes(event.start, event.end)

        logger.debug("event.update start", extra={"uid": uid, "calendar": calendar_name, "user": auth.credentials.username})
        
        if event.uid and event.uid != uid:
            res_txt = f"UID in path ({uid}) doesn't match event UID ({event.uid})"
            logger.error(res_txt)
            raise HTTPException(
                status_code=400,
                detail=res_txt
            )
        logger.debug(f"Updating event with UID: {uid}")
        
        await _ensure_calendar_exists(calendar_name, auth)
        
        if not event.uid:
            event.uid = uid
        
        updated_event = await run_nextcloud_call(
            "update event",
            update_event,
            credentials=auth.credentials,
            event=event,
            calendar_name=calendar_name,
            user_info=auth.user_info,
        )
        
        invalidate_event_caches_for_user(auth.credentials.username)
        return updated_event
    finally:
        logger.debug(
            "event.update done",
            extra={"uid": uid, "calendar": calendar_name, "user": auth.credentials.username, "elapsed_ms": int((perf_counter() - start_time) * 1000)},
        )


@router.post(
    "/recurring/{uid}/exception",
    operation_id="upsert_recurrence_exception",
    response_model=Event,
    summary="Upsert recurrence exception",
    description="Create or update a single occurrence override for a recurring event using RECURRENCE-ID.",
    tags=["events"],
)
async def upsert_recurrence_exception_endpoint(
    payload: RecurrenceExceptionRequest,
    uid: str = Path(
        ...,
        description="UID of the recurring event",
        min_length=3,
        max_length=255,
        regex=r"^[A-Za-z0-9._\\-]{3,255}$",
    ),
    calendar_name: str = Query(
        "personal",
        description="Calendar containing the recurring event",
        example="personal",
        max_length=100,
        min_length=1,
    ),
    auth: AuthContext = Depends(authenticated_user),
):
    """Create or update a recurrence exception."""
    if not calendar_name.strip():
        raise HTTPException(status_code=400, detail="Calendar name must not be empty")
    await _ensure_calendar_exists(calendar_name, auth)
    overrides = payload.model_dump(exclude={"recurrence_id"}, exclude_none=True)
    updated = await run_nextcloud_call(
        "upsert recurrence exception",
        upsert_recurrence_exception,
        credentials=auth.credentials,
        uid=uid,
        recurrence_id=payload.recurrence_id,
        overrides=overrides,
        calendar_name=calendar_name,
        user_info=auth.user_info,
    )
    invalidate_event_caches_for_user(auth.credentials.username)
    return updated


@router.post(
    "/recurring/{uid}/skip",
    operation_id="skip_recurrence_instances",
    response_model=Event,
    summary="Skip recurrence instances",
    description="Skip one or more recurrence instances by adding EXDATE entries to the master event.",
    tags=["events"],
)
async def skip_recurrence_instances_endpoint(
    payload: RecurrenceSkipRequest,
    uid: str = Path(
        ...,
        description="UID of the recurring event",
        min_length=3,
        max_length=255,
        regex=r"^[A-Za-z0-9._\\-]{3,255}$",
    ),
    calendar_name: str = Query(
        "personal",
        description="Calendar containing the recurring event",
        example="personal",
        max_length=100,
        min_length=1,
    ),
    auth: AuthContext = Depends(authenticated_user),
):
    """Add EXDATE entries to skip recurrence instances."""
    if not calendar_name.strip():
        raise HTTPException(status_code=400, detail="Calendar name must not be empty")
    await _ensure_calendar_exists(calendar_name, auth)
    updated = await run_nextcloud_call(
        "skip recurrence instances",
        skip_recurrence_instances,
        credentials=auth.credentials,
        uid=uid,
        recurrence_ids=payload.recurrence_ids,
        calendar_name=calendar_name,
        user_info=auth.user_info,
    )
    invalidate_event_caches_for_user(auth.credentials.username)
    return updated


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
        **EVENT_ERROR_RESPONSES,
        404: {
            "description": "Event not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Event with UID 550e8400-e29b-41d4-a716-446655440000 not found"}
                }
            },
        },
    },
    tags=["events"],
)
async def delete_event_endpoint(
    uid: str = Path(
        ...,
        description="Unique identifier for the event",
        example="550e8400-e29b-41d4-a716-446655440000",
        min_length=3,
        max_length=255,
        regex=r"^[A-Za-z0-9._\\-]{3,255}$",
    ),
    calendar_name: str = Query(
        "personal",
        description="Optional calendar name to delete the event from a specific calendar",
        example="personal",
        max_length=100,
        min_length=1,
    ),
    auth: AuthContext = Depends(authenticated_user)
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
    - Optional privacy mode for sensitive data masking
    
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
    
    **Note:** When privacy mode is enabled, certain sensitive fields may be masked
    or omitted from the response to protect confidential information.
    """
    start_time = perf_counter()
    try:
        if not calendar_name.strip():
            raise HTTPException(status_code=400, detail="Calendar name must not be empty")
        logger.debug(f"Deleting event with UID: {uid}")
        
        await _ensure_calendar_exists(calendar_name, auth)
        
        result = await run_nextcloud_call(
            "delete event",
            delete_event,
            credentials=auth.credentials,
            uid=uid,
            calendar_name=calendar_name,
            user_info=auth.user_info,
        )
        
        if not result:
            res_txt = f"Event with UID {uid} not found"
            logger.error(res_txt)
            raise HTTPException(status_code=404, detail=res_txt)
        
        invalidate_event_caches_for_user(auth.credentials.username)
        return None
    finally:
        logger.debug(
            "event.delete done",
            extra={"uid": uid, "calendar": calendar_name, "user": auth.credentials.username, "elapsed_ms": int((perf_counter() - start_time) * 1000)},
        )
