# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

from fastapi import APIRouter, HTTPException, Depends, Path, Query, Response
from time import perf_counter
from typing import List

from src import logger
from src.api.responses import TASK_ERROR_RESPONSES
from src.common.cache import (
    build_cache_key,
    get_task_caches,
    invalidate_task_caches_for_user,
    set_cache_headers,
)
from src.common.nextcloud_utils import run_nextcloud_call
from src.common.validation import validate_time_range, validate_task_datetimes
from src.dependencies.auth import authenticated_user, AuthContext
from src.models.task import Task
from src.models.event import (
    RecurrenceInstance,
    RecurrencePreviewRequest,
    RecurrenceRuleRequest,
    RecurrenceSkipRequest,
    RecurrencePreviewResponse,
)
from src.models.task import TaskRecurrenceExceptionRequest
from src.nextcloud.tasks import (
    get_task_by_uid,
    get_tasks_by_time_range,
    create_task,
    update_task,
    delete_task,
    list_calendars,
    expand_task_recurrence_instances,
    preview_task_recurrence,
    build_task_recurrence_rule,
    upsert_task_recurrence_exception,
    skip_task_recurrence_instances,
)


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


router = APIRouter()


@router.get(
    "/calendars",
    operation_id="list_task_calendars",
    summary="List calendars for the authenticated user",
    description="Discover all CalDAV calendars visible to the authenticated user for tasks (VTODO collections).",
    tags=["tasks"],
    responses={
        200: {"description": "Calendars retrieved successfully"},
        **TASK_ERROR_RESPONSES,
    },
)
async def list_calendars_endpoint(
    response: Response,
    auth: AuthContext = Depends(authenticated_user),
):
    """Return all calendars the authenticated user can access (shared with events)."""
    start_time = perf_counter()
    caches = get_task_caches()
    cache_key = build_cache_key(auth.credentials.username, "calendars")
    if cache_key in caches.calendars:
        set_cache_headers(response, caches.calendars, cache_key, hit=True)
        logger.debug("task calendars cache hit", extra={"user": auth.credentials.username})
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
            "task.calendars.done",
            extra={"user": auth.credentials.username, "elapsed_ms": int((perf_counter() - start_time) * 1000)},
        )


@router.get(
    "/{uid}",
    operation_id="get_task_by_uid",
    response_model=Task,
    summary="Get task by UID",
    description="Retrieve a single task (VTODO) by its unique identifier",
    responses={
        200: {
            "description": "Task retrieved successfully",
            "model": Task,
        },
        400: {
            "description": "Invalid UID format",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid UID format provided"}
                }
            },
        },
        **TASK_ERROR_RESPONSES,
        404: {
            "description": "Task not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Task with UID 550e8400-e29b-41d4-a716-446655440000 not found"}
                }
            },
        },
    },
    tags=["tasks"],
)
async def read_task_endpoint(
    response: Response,
    uid: str = Path(
        ...,
        description="Unique identifier for the task",
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
        description="Optional calendar name to filter tasks from a specific calendar",
        example="personal",
        max_length=100,
        min_length=1,
    ),
):
    start_time = perf_counter()
    try:
        logger.debug("task.get start", extra={"uid": uid, "calendar": calendar_name, "user": auth.credentials.username, "privacy": privacy})
        if not calendar_name.strip():
            raise HTTPException(status_code=400, detail="Calendar name must not be empty")
        await _ensure_calendar_exists(calendar_name, auth)

        caches = get_task_caches()
        cache_key = build_cache_key(auth.credentials.username, "task", uid, calendar_name, str(privacy))
        if cache_key in caches.by_uid:
            if response:
                set_cache_headers(response, caches.by_uid, cache_key, hit=True)
            return caches.by_uid[cache_key]

        task = await run_nextcloud_call(
            "retrieve task",
            get_task_by_uid,
            credentials=auth.credentials,
            uid=uid,
            calendar_name=calendar_name,
            privacy=privacy,
            user_info=auth.user_info,
        )

        if task is None:
            res_txt = f"Task with UID {uid} not found"
            logger.error(res_txt)
            raise HTTPException(status_code=404, detail=res_txt)

        caches.by_uid[cache_key] = task
        if response:
            set_cache_headers(response, caches.by_uid, cache_key, hit=False)
        return task
    finally:
        logger.debug(
            "task.get done",
            extra={"uid": uid, "calendar": calendar_name, "user": auth.credentials.username, "elapsed_ms": int((perf_counter() - start_time) * 1000)},
        )


@router.get(
    "/",
    operation_id="get_tasks_by_timerange",
    response_model=List[Task],
    summary="Get tasks by time range",
    description="Retrieve tasks within a specified date/time range (uses CalDAV VTODO time-range filtering)",
    responses={
        200: {
            "description": "Tasks retrieved successfully",
            "model": List[Task],
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
        **TASK_ERROR_RESPONSES,
    },
    tags=["tasks"],
)
async def read_tasks_by_time_range_endpoint(
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
        description="Optional calendar name to filter tasks from a specific calendar",
        example="personal",
        max_length=100,
        min_length=1,
    ),
):
    start_time = perf_counter()
    try:
        logger.debug(
            "task.range start",
            extra={"user": auth.credentials.username, "calendar": calendar_name, "start": start_datetime, "end": end_datetime, "privacy": privacy},
        )
        if not calendar_name.strip():
            raise HTTPException(status_code=400, detail="Calendar name must not be empty")
        validate_time_range(start_datetime, end_datetime, label_prefix="Time range")
        await _ensure_calendar_exists(calendar_name, auth)
        caches = get_task_caches()
        cache_key = build_cache_key(auth.credentials.username, "tasks_range", start_datetime, end_datetime, calendar_name or "", str(privacy))
        if cache_key in caches.by_range:
            if response:
                set_cache_headers(response, caches.by_range, cache_key, hit=True)
            return caches.by_range[cache_key]

        tasks = await run_nextcloud_call(
            "retrieve tasks",
            get_tasks_by_time_range,
            calendar_name=calendar_name,
            credentials=auth.credentials,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            privacy=privacy,
            user_info=auth.user_info,
        )

        caches.by_range[cache_key] = tasks
        if response:
            set_cache_headers(response, caches.by_range, cache_key, hit=False)
        return tasks
    finally:
        logger.debug(
            "task.range done",
            extra={"user": auth.credentials.username, "calendar": calendar_name, "elapsed_ms": int((perf_counter() - start_time) * 1000)},
        )


@router.get(
    "/recurring/{uid}/instances",
    operation_id="get_recurring_task_instances",
    response_model=List[RecurrenceInstance],
    summary="Expand recurring task instances",
    description="Expand a recurring task into concrete occurrences between the provided start and end datetimes.",
    tags=["tasks"],
)
async def get_recurring_task_instances_endpoint(
    response: Response,
    uid: str = Path(
        ...,
        description="UID of the recurring task to expand",
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
        description="Calendar containing the recurring task",
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
    """Expand recurring task instances within a window."""
    start_time = perf_counter()
    try:
        if not calendar_name.strip():
            raise HTTPException(status_code=400, detail="Calendar name must not be empty")
        validate_time_range(start_datetime, end_datetime, label_prefix="Time range")
        await _ensure_calendar_exists(calendar_name, auth)
        caches = get_task_caches()
        cache_key = build_cache_key(auth.credentials.username, "tasks_recurring", uid, start_datetime, end_datetime, calendar_name, str(privacy))
        if cache_key in caches.by_range:
            set_cache_headers(response, caches.by_range, cache_key, hit=True)
            return caches.by_range[cache_key]
        instances = await run_nextcloud_call(
            "expand recurring task instances",
            expand_task_recurrence_instances,
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
            "task.recurrence.instances done",
            extra={"uid": uid, "calendar": calendar_name, "user": auth.credentials.username, "elapsed_ms": int((perf_counter() - start_time) * 1000)},
        )


@router.post(
    "/recurring/preview",
    operation_id="preview_task_recurrence_rule",
    response_model=RecurrencePreviewResponse,
    summary="Preview task recurrence rule",
    description="Generate an RRULE and preview task occurrences using either a raw RRULE string or a friendly recurrence payload.",
    tags=["tasks"],
)
async def preview_task_recurrence_endpoint(
    payload: RecurrencePreviewRequest,
    auth: AuthContext = Depends(authenticated_user),
):
    """Build and preview recurrence occurrences for tasks."""
    preview = preview_task_recurrence(
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
    operation_id="build_task_recurrence_rule",
    summary="Build task recurrence rule from friendly fields",
    description="Generate an RRULE string and short summary from a friendly recurrence payload for tasks.",
    tags=["tasks"],
)
async def build_task_recurrence_rule_endpoint(
    payload: RecurrenceRuleRequest,
    auth: AuthContext = Depends(authenticated_user),
):
    """Build an RRULE string from a friendly payload for tasks."""
    return build_task_recurrence_rule(payload.friendly)


@router.post(
    "/",
    operation_id="create_task",
    response_model=Task,
    status_code=201,
    summary="Create a new task",
    description="Create a new task (VTODO) in the Nextcloud CalDAV calendar",
    responses={
        201: {
            "description": "Task created successfully",
            "model": Task,
        },
        400: {
            "description": "Invalid task data",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_datetime": {
                            "summary": "Invalid datetime format",
                            "value": {"detail": "Invalid datetime format in start field"}
                        },
                        "missing_required": {
                            "summary": "Missing required fields",
                            "value": {"detail": "Task summary is required"}
                        },
                        "invalid_range": {
                            "summary": "Invalid time range",
                            "value": {"detail": "Task due time must be on or after start time"}
                        }
                    }
                }
            },
        },
        **TASK_ERROR_RESPONSES,
    },
    tags=["tasks"],
)
async def create_task_endpoint(
    task: Task,
    calendar_name: str = Query(
        "personal",
        description="Optional calendar name to create the task in a specific calendar",
        example="personal",
        max_length=100,
        min_length=1,
    ),
    auth: AuthContext = Depends(authenticated_user)
):
    start_time = perf_counter()
    try:
        if not calendar_name.strip():
            raise HTTPException(status_code=400, detail="Calendar name must not be empty")
        if task.categories:
            for cat in task.categories:
                if len(cat or "") > 64:
                    raise HTTPException(status_code=400, detail="Category values must be <=64 characters")
        validate_task_datetimes(task.start, task.due, label_prefix="Task")

        logger.debug(
            "task.create start",
            extra={"user": auth.credentials.username, "calendar": calendar_name, "uid": task.uid},
        )
        await _ensure_calendar_exists(calendar_name, auth)

        created_task = await run_nextcloud_call(
            "create task",
            create_task,
            credentials=auth.credentials,
            task=task,
            calendar_name=calendar_name,
            user_info=auth.user_info,
        )

        invalidate_task_caches_for_user(auth.credentials.username)
        return created_task
    finally:
        logger.debug(
            "task.create done",
            extra={"user": auth.credentials.username, "calendar": calendar_name, "uid": task.uid, "elapsed_ms": int((perf_counter() - start_time) * 1000)},
        )


@router.put(
    "/{uid}",
    operation_id="update_task_by_uid",
    response_model=Task,
    summary="Update an existing task",
    description="Update an existing task in the Nextcloud CalDAV calendar",
    responses={
        200: {
            "description": "Task updated successfully",
            "model": Task,
        },
        400: {
            "description": "Invalid task data or UID mismatch",
            "content": {
                "application/json": {
                    "examples": {
                        "uid_mismatch": {
                            "summary": "UID mismatch between path and task data",
                            "value": {"detail": "UID mismatch: 550e8400-e29b-41d4-a716-446655440000 in path vs 123e4567-e89b-12d3-a456-426614174000 in task data"}
                        },
                        "invalid_datetime": {
                            "summary": "Invalid datetime format",
                            "value": {"detail": "Invalid datetime format in start field"}
                        },
                        "invalid_range": {
                            "summary": "Invalid time range",
                            "value": {"detail": "Task due time must be on or after start time"}
                        }
                    }
                }
            },
        },
        **TASK_ERROR_RESPONSES,
        404: {
            "description": "Task not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Task with UID 550e8400-e29b-41d4-a716-446655440000 not found"}
                }
            },
        },
    },
    tags=["tasks"],
)
async def update_task_endpoint(
    task: Task,
    uid: str = Path(
        ...,
        description="Unique identifier for the task",
        example="550e8400-e29b-41d4-a716-446655440000",
        min_length=3,
        max_length=255,
        regex=r"^[A-Za-z0-9._\\-]{3,255}$",
    ),
    calendar_name: str = Query(
        "personal",
        description="Optional calendar name to update the task in a specific calendar",
        example="personal",
        max_length=100,
        min_length=1,
    ),
    auth: AuthContext = Depends(authenticated_user)
):
    start_time = perf_counter()
    try:
        if not calendar_name.strip():
            raise HTTPException(status_code=400, detail="Calendar name must not be empty")
        if task.categories:
            for cat in task.categories:
                if len(cat or "") > 64:
                    raise HTTPException(status_code=400, detail="Category values must be <=64 characters")
        validate_task_datetimes(task.start, task.due, label_prefix="Task")

        logger.debug("task.update start", extra={"uid": uid, "calendar": calendar_name, "user": auth.credentials.username})

        if task.uid and task.uid != uid:
            res_txt = f"UID in path ({uid}) doesn't match task UID ({task.uid})"
            logger.error(res_txt)
            raise HTTPException(
                status_code=400,
                detail=res_txt
            )
        logger.debug("Updating task with UID: %s", uid)

        await _ensure_calendar_exists(calendar_name, auth)

        if not task.uid:
            task.uid = uid

        updated_task = await run_nextcloud_call(
            "update task",
            update_task,
            credentials=auth.credentials,
            task=task,
            calendar_name=calendar_name,
            user_info=auth.user_info,
        )

        invalidate_task_caches_for_user(auth.credentials.username)
        return updated_task
    finally:
        logger.debug(
            "task.update done",
            extra={"uid": uid, "calendar": calendar_name, "user": auth.credentials.username, "elapsed_ms": int((perf_counter() - start_time) * 1000)},
        )


@router.post(
    "/recurring/{uid}/exception",
    operation_id="upsert_task_recurrence_exception",
    response_model=Task,
    summary="Upsert recurring task exception",
    description="Create or update a single occurrence override for a recurring task using RECURRENCE-ID.",
    tags=["tasks"],
)
async def upsert_task_recurrence_exception_endpoint(
    payload: TaskRecurrenceExceptionRequest,
    uid: str = Path(
        ...,
        description="UID of the recurring task",
        min_length=3,
        max_length=255,
        regex=r"^[A-Za-z0-9._\\-]{3,255}$",
    ),
    calendar_name: str = Query(
        "personal",
        description="Calendar containing the recurring task",
        example="personal",
        max_length=100,
        min_length=1,
    ),
    auth: AuthContext = Depends(authenticated_user),
):
    """Create or update a recurrence exception for a task."""
    if not calendar_name.strip():
        raise HTTPException(status_code=400, detail="Calendar name must not be empty")
    await _ensure_calendar_exists(calendar_name, auth)
    overrides = payload.model_dump(exclude={"recurrence_id"}, exclude_none=True)
    updated = await run_nextcloud_call(
        "upsert recurrence exception",
        upsert_task_recurrence_exception,
        credentials=auth.credentials,
        uid=uid,
        recurrence_id=payload.recurrence_id,
        overrides=overrides,
        calendar_name=calendar_name,
        user_info=auth.user_info,
    )
    invalidate_task_caches_for_user(auth.credentials.username)
    return updated


@router.post(
    "/recurring/{uid}/skip",
    operation_id="skip_task_recurrence_instances",
    response_model=Task,
    summary="Skip recurrence task instances",
    description="Skip one or more recurrence instances by adding EXDATE entries to the master task.",
    tags=["tasks"],
)
async def skip_task_recurrence_instances_endpoint(
    payload: RecurrenceSkipRequest,
    uid: str = Path(
        ...,
        description="UID of the recurring task",
        min_length=3,
        max_length=255,
        regex=r"^[A-Za-z0-9._\\-]{3,255}$",
    ),
    calendar_name: str = Query(
        "personal",
        description="Calendar containing the recurring task",
        example="personal",
        max_length=100,
        min_length=1,
    ),
    auth: AuthContext = Depends(authenticated_user),
):
    """Add EXDATE entries to skip recurrence instances for tasks."""
    if not calendar_name.strip():
        raise HTTPException(status_code=400, detail="Calendar name must not be empty")
    await _ensure_calendar_exists(calendar_name, auth)
    updated = await run_nextcloud_call(
        "skip recurrence instances",
        skip_task_recurrence_instances,
        credentials=auth.credentials,
        uid=uid,
        recurrence_ids=payload.recurrence_ids,
        calendar_name=calendar_name,
        user_info=auth.user_info,
    )
    invalidate_task_caches_for_user(auth.credentials.username)
    return updated


@router.delete(
    "/{uid}",
    operation_id="delete_task_by_uid",
    status_code=204,
    summary="Delete a task",
    description="Delete a task (VTODO) from the Nextcloud CalDAV calendar",
    responses={
        204: {
            "description": "Task deleted successfully",
        },
        400: {
            "description": "Invalid UID format",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid UID format provided"}
                }
            },
        },
        **TASK_ERROR_RESPONSES,
        404: {
            "description": "Task not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Task with UID 550e8400-e29b-41d4-a716-446655440000 not found"}
                }
            },
        },
    },
    tags=["tasks"],
)
async def delete_task_endpoint(
    uid: str = Path(
        ...,
        description="Unique identifier for the task",
        example="550e8400-e29b-41d4-a716-446655440000",
        min_length=3,
        max_length=255,
        regex=r"^[A-Za-z0-9._\\-]{3,255}$",
    ),
    calendar_name: str = Query(
        "personal",
        description="Optional calendar name to delete the task from a specific calendar",
        example="personal",
        max_length=100,
        min_length=1,
    ),
    auth: AuthContext = Depends(authenticated_user)
):
    start_time = perf_counter()
    try:
        if not calendar_name.strip():
            raise HTTPException(status_code=400, detail="Calendar name must not be empty")
        logger.debug("Deleting task with UID: %s", uid)

        await _ensure_calendar_exists(calendar_name, auth)

        result = await run_nextcloud_call(
            "delete task",
            delete_task,
            credentials=auth.credentials,
            uid=uid,
            calendar_name=calendar_name,
            user_info=auth.user_info,
        )

        if not result:
            res_txt = f"Task with UID {uid} not found"
            logger.error(res_txt)
            raise HTTPException(status_code=404, detail=res_txt)

        invalidate_task_caches_for_user(auth.credentials.username)
        return None
    finally:
        logger.debug(
            "task.delete done",
            extra={"uid": uid, "calendar": calendar_name, "user": auth.credentials.username, "elapsed_ms": int((perf_counter() - start_time) * 1000)},
        )
