# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Models Package

This package contains all Pydantic models used throughout the application for:
- Data validation and serialization
- API request/response schemas
- Parameter validation for endpoints

Modules:
- contact: Contact-related models and search criteria
- event: Event-related models and search criteria  
- api_params: API parameter models for path and query parameters
"""

from .contact import Contact, ContactSearchCriteria, Address, Email, Phone
from .event import Event, EventSearchCriteria, Attendee, Reminder
from .api_params import UidParam, DateTimeRangeParams, EventsQueryParams, ContactsQueryParams, StatusQueryParams

__all__ = [
    # Contact models
    "Contact",
    "ContactSearchCriteria", 
    "Address",
    "Email",
    "Phone",
    
    # Event models
    "Event",
    "EventSearchCriteria",
    "Attendee", 
    "Reminder",
    
    # API parameter models
    "UidParam",
    "DateTimeRangeParams",
    "EventsQueryParams",
    "ContactsQueryParams",
    "StatusQueryParams",
]