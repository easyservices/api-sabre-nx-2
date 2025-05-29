# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Contact Models Module

This module defines the data models for contacts and related entities used throughout the application.
It provides Pydantic models for type validation, serialization, and deserialization of contact data
retrieved from or sent to CardDAV servers.

The module includes:
- Contact: The main contact model with personal information
- Address: Physical address information
- Email: Email address with type tag
- Phone: Phone number with type tag
- ContactSearchCriteria: Model for specifying search parameters
"""

from typing import List, Optional, Literal
import uuid
from pydantic import BaseModel, Field

class Address(BaseModel):
    """
    Physical address information for a contact.
    
    All fields are optional to accommodate various address formats and partial information.
    """
    tag: Optional[str] = Field(None, description="Address type (e.g., 'home', 'work', 'other')")
    street: Optional[str] = Field(None, description="Street address including house number")
    city: Optional[str] = Field(None, description="City or locality")
    state: Optional[str] = Field(None, description="State, province, or region")
    postal_code: Optional[str] = Field(None, description="Postal or ZIP code")
    country: Optional[str] = Field(None, description="Country name")

class Email(BaseModel):
    """
    Email address information for a contact.
    """
    tag: Optional[str] = Field(None, description="Email type (e.g., 'home', 'work', 'other')")
    email: Optional[str] = Field(None, description="Email address")

class Phone(BaseModel):
    """
    Phone number information for a contact.
    """
    tag: Optional[str] = Field(None, description="Phone type (e.g., 'cell', 'home', 'work', 'fax')")
    number: Optional[str] = Field(None, description="Phone number")

class Contact(BaseModel):
    """
    Main contact model representing a person or entity.
    
    This model contains all the information about a contact, including personal details,
    communication methods, and organizational information. It maps to a vCard in the
    CardDAV protocol.
  
    """
    uid: str = Field(..., description="Unique identifier for the contact")
    full_name: str = Field(..., description="Full name of the contact")
    vcs_uri: Optional[str] = Field(None, description="URI of the vCard on the CardDAV server")
    emails: Optional[List[Email]] = Field(None, description="List of email addresses")
    phones: Optional[List[Phone]] = Field(None, description="List of phone numbers")
    addresses: Optional[List[Address]] = Field(None, description="List of physical addresses")
    birthday: Optional[str] = Field(None, description="Birthday in YYYY-MM-DD format")
    notes: Optional[str] = Field(None, description="Additional notes about the contact")
    groups: Optional[List[str]] = Field(None, description="List of groups/categories the contact belongs to")
    
    @classmethod
    def generate_uid(cls) -> str:
        """
        Generate a unique identifier (UUID4) for a contact.
        
        Returns:
            str: A string representation of a UUID4
        """
        return str(uuid.uuid4())

class ContactSearchCriteria(BaseModel):
    """
    Search criteria for contacts.
    
    This model defines the fields that can be used to search for contacts in a CardDAV server.
    All fields are optional and case-insensitive partial matches are used for string fields.
    
    The search_type field determines whether to use OR logic ("anyof") or AND logic ("allof")
    when multiple search criteria are provided.

    """
    uid: Optional[str] = Field(None, description="Search by contact UID (case-insensitive partial match)")
    full_name: Optional[str] = Field(None, description="Search by contact's full name (case-insensitive partial match)")
    email: Optional[str] = Field(None, description="Search by any email address (case-insensitive partial match)")
    phone: Optional[str] = Field(None, description="Search by any phone number (case-insensitive partial match)")
    address: Optional[str] = Field(None, description="Search by any address field (case-insensitive partial match)")
    birthday: Optional[str] = Field(None, description="Search by birthday (case-insensitive partial match)")
    group: Optional[str] = Field(None, description="Search by group/category (case-insensitive partial match)")
    search_type: Optional[Literal["anyof", "allof"]] = Field(
        default="anyof",
        description="Search logic: 'anyof' (OR) means any criteria can match, 'allof' (AND) means all criteria must match"
    )
    
    def to_dict(self):
        """
        Convert to dictionary, excluding None values and search_type.
        
        Returns:
            dict: Dictionary containing only the non-None search criteria fields,
                  excluding the search_type field which is handled separately.
        """
        return {k: v for k, v in self.model_dump().items()
                if v is not None and k != "search_type"}