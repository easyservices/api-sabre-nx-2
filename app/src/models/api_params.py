# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
API Parameters Models Module

This module defines Pydantic models for API endpoint parameters including path parameters,
query parameters, and request bodies. These models provide validation, documentation,
and type safety for the FastAPI endpoints.

The module includes:
- UidParam: Path parameter for UID values
- DateTimeRangeParams: Query parameters for datetime range filtering
- ContactsQueryParams: Query parameters for contacts endpoints
- EventsQueryParams: Query parameters for events endpoints

Benefits of using Pydantic for API parameters:
1. Automatic validation of parameter types and formats
2. Rich error messages for invalid parameters
3. Automatic OpenAPI/Swagger documentation generation
4. Type safety and IDE autocompletion
5. Consistent parameter handling across endpoints
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator, validator
from datetime import datetime
import re
from src import logger


class UidParam(BaseModel):
    """
    Path parameter model for UID values.
    
    Used for endpoints that require a UID in the path like /contacts/{uid} or /events/{uid}.
    Validates that the UID is a non-empty string with reasonable length constraints.
    """
    uid: str = Field(
        ...,
        description="Unique identifier (UID) for the resource",
        min_length=1,
        max_length=255,
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"}
    )
    
    @field_validator('uid')
    def validate_uid_format(cls, v):
        """Validate UID format - should not contain invalid characters."""
        if not v or not v.strip():
            raise ValueError("UID cannot be empty or whitespace only")
        
        # Check for potentially problematic characters in URLs
        invalid_chars = ['/', '\\', '?', '#', '[', ']', '@', '!', '$', '&', "'", '(', ')', '*', '+', ',', ';', '=']
        for char in invalid_chars:
            if char in v:
                raise ValueError(f"UID contains invalid character: '{char}'")
        
        return v.strip()


class DateTimeRangeParams(BaseModel):
    """
    Query parameters for datetime range filtering.
    
    Used for endpoints that need to filter by date/time ranges.
    """
    start_datetime: str = Field(
        ...,
        description="Start datetime in ISO format (YYYY-MM-DDTHH:MM:SS)",
        json_schema_extra={"example": "2025-04-21T00:00:00"}
    )
    end_datetime: str = Field(
        ...,
        description="End datetime in ISO format (YYYY-MM-DDTHH:MM:SS)",
        json_schema_extra={"example": "2025-04-28T23:59:59"}
    )
    
    @field_validator('start_datetime', 'end_datetime')
    def validate_datetime_format(cls, v):
        """Validate that datetime strings are in correct ISO format."""
        try:
            datetime.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid datetime format: {v}. Expected ISO format (YYYY-MM-DDTHH:MM:SS)")
    
    @field_validator('end_datetime')
    def validate_end_after_start(cls, v, values):
        """Validate that end_datetime is after start_datetime."""
        if 'start_datetime' in values:
            start_dt = datetime.fromisoformat(values['start_datetime'])
            end_dt = datetime.fromisoformat(v)
            if end_dt <= start_dt:
                raise ValueError("end_datetime must be after start_datetime")
        return v


class EventsQueryParams(BaseModel):
    """
    Query parameters for events endpoints.
    
    Combines datetime range filtering with optional calendar selection.
    """
    start_datetime: str = Field(
        ...,
        description="Start datetime in ISO format (YYYY-MM-DDTHH:MM:SS)",
        json_schema_extra={"example": "2025-04-21T00:00:00"}
    )
    end_datetime: str = Field(
        ...,
        description="End datetime in ISO format (YYYY-MM-DDTHH:MM:SS)",
        json_schema_extra={"example": "2025-04-28T23:59:59"}
    )
    calendar_name: Optional[str] = Field(
        None,
        description="Optional calendar name to filter events from a specific calendar",
        json_schema_extra={"example": "personal"}
    )
    
    @field_validator('start_datetime', 'end_datetime')
    def validate_datetime_format(cls, v):
        """Validate that datetime strings are in correct ISO format."""
        try:
            datetime.fromisoformat(v)
            return v
        except ValueError:
            raise ValueError(f"Invalid datetime format: {v}. Expected ISO format (YYYY-MM-DDTHH:MM:SS)")
    
    @field_validator('end_datetime')
    def validate_end_after_start(cls, v, values):
        """Validate that end_datetime is after start_datetime."""
        if 'start_datetime' in values:
            start_dt = datetime.fromisoformat(values['start_datetime'])
            end_dt = datetime.fromisoformat(v)
            if end_dt <= start_dt:
                raise ValueError("end_datetime must be after start_datetime")
        return v


class ContactsQueryParams(BaseModel):
    """
    Query parameters for contacts endpoints.
    
    Currently empty but can be extended for future filtering needs.
    """
    pass


class StatusQueryParams(BaseModel):
    """
    Query parameters for status endpoint.
    
    Currently empty but can be extended for future status filtering needs.
    """
    pass