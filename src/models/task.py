# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Task Models Module

Defines Pydantic models for Nextcloud tasks (VTODO). Mirrors the event model
surface where appropriate to keep the API symmetric with /events.
"""

from typing import List, Optional
from datetime import datetime
import uuid

from pydantic import BaseModel, Field, model_validator

from src.models.event import Attendee, Reminder
from src.models.event import RecurrenceSkipRequest, RecurrencePreviewRequest, RecurrenceRuleRequest, RecurrencePreviewResponse, FriendlyRecurrence, RecurrenceInstance


class Task(BaseModel):
    """Main task model representing a VTODO."""

    uid: str = Field(..., description="Unique identifier for the task")
    summary: str = Field(..., description="Title or summary of the task")
    description: Optional[str] = Field(None, description="Detailed description of the task")
    status: Optional[str] = Field(None, description="Task status (e.g., 'NEEDS-ACTION', 'IN-PROCESS', 'COMPLETED', 'CANCELLED')")
    url: Optional[str] = Field(None, description="URL of the task on the CalDAV server")

    # Timing information
    start: Optional[str] = Field(None, description="Optional start/due-from time in ISO format (YYYY-MM-DDTHH:MM:SS)")
    due: Optional[str] = Field(None, description="Optional due time/date in ISO format (YYYY-MM-DDTHH:MM:SS)")
    completed: Optional[str] = Field(None, description="Completion timestamp in ISO format if the task is completed")
    all_day: Optional[bool] = Field(False, description="Whether the task uses date-only fields (all-day)")
    created: Optional[str] = Field(None, description="Creation time of the task in ISO format")
    last_modified: Optional[str] = Field(None, description="Last modification time of the task in ISO format")

    # Metadata
    percent_complete: Optional[int] = Field(None, description="Percentage completion (0-100)")
    priority: Optional[int] = Field(None, description="Task priority (0-9, lower is higher priority)")
    categories: Optional[List[str]] = Field(None, description="List of categories/tags for the task")
    organizer: Optional[str] = Field(None, description="Email of the task organizer")

    # Participants and notifications
    attendees: Optional[List[Attendee]] = Field(None, description="List of task attendees")
    reminders: Optional[List[Reminder]] = Field(None, description="List of reminders/alarms for the task")

    # Recurrence
    recurrence: Optional[str] = Field(None, description="Recurrence rule for repeating tasks (RRULE)")
    recurrence_id: Optional[str] = Field(None, description="For instances of recurring tasks, the original task's date/time")
    exdate: Optional[List[str]] = Field(None, description="List of ISO datetimes excluded from recurrence expansion")

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        candidate = value
        if candidate.endswith("Z"):
            candidate = f"{candidate[:-1]}+00:00"
        return datetime.fromisoformat(candidate)

    @model_validator(mode="after")
    def check_temporal_fields(self):
        """Ensure temporal fields are valid and percent/priority are within bounds."""
        try:
            start_dt = self._parse_datetime(self.start) if self.start else None
            due_dt = self._parse_datetime(self.due) if self.due else None
        except Exception as exc:  # pragma: no cover - defensive parsing
            raise ValueError(f"Invalid datetime value: {exc}") from exc

        if start_dt and due_dt:
            if (start_dt.tzinfo is None) != (due_dt.tzinfo is None):
                raise ValueError("Task start and due must both include a timezone or neither")
            if due_dt < start_dt:
                raise ValueError("Task due time must be on or after start time")

        if self.percent_complete is not None:
            if not (0 <= self.percent_complete <= 100):
                raise ValueError("percent_complete must be between 0 and 100")

        if self.priority is not None:
            if not (0 <= self.priority <= 9):
                raise ValueError("priority must be between 0 (undefined) and 9")

        return self

    @classmethod
    def generate_uid(cls) -> str:
        """Generate a UUID4 UID for a task."""
        return str(uuid.uuid4())


class TaskRecurrenceExceptionRequest(BaseModel):
    """
    Payload to upsert an exception instance for a recurring task.
    """
    recurrence_id: str = Field(..., description="RECURRENCE-ID of the occurrence to override (ISO datetime)")
    summary: Optional[str] = Field(None, description="Override summary/title")
    description: Optional[str] = Field(None, description="Override description")
    status: Optional[str] = Field(None, description="Override status")
    start: Optional[str] = Field(None, description="Override start datetime")
    due: Optional[str] = Field(None, description="Override due datetime")
    all_day: Optional[bool] = Field(None, description="Override all-day flag")
    categories: Optional[List[str]] = Field(None, description="Override categories")
    attendees: Optional[List[Attendee]] = Field(None, description="Override attendees list")
    reminders: Optional[List[Reminder]] = Field(None, description="Override reminders list")
    percent_complete: Optional[int] = Field(None, description="Override percent complete")
    priority: Optional[int] = Field(None, description="Override priority")

    @model_validator(mode="after")
    def ensure_override_fields(self):
        overrides = self.model_dump(exclude={"recurrence_id"}, exclude_none=True)
        if not overrides:
            raise ValueError("At least one override field must be provided")
        return self
