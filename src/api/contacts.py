# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

from fastapi import APIRouter, HTTPException, Depends, Path, Query
from typing import List, Optional

from fastapi.security import HTTPBasicCredentials
from src.common import security

from src.common.sec import authenticate_with_nextcloud
from src.models.contact import Contact, ContactSearchCriteria
from src.models.api_params import UidParam
from src.nextcloud.contacts import get_all_contacts, search_contacts, create_contact, update_contact, delete_contact, get_contact_by_uid
# import all you need from fastapi-pagination
from fastapi_pagination import Page, paginate


IS_DEBUG = False

# --- Router Definition ---
# We're using the get_user_settings dependency directly in each endpoint
# instead of applying validate_api_key to all routes
router = APIRouter()

@router.post(
    "/",
    operation_id="create_contact",
    response_model=Contact,
    status_code=201,
    summary="Create a new contact",
    description="Create a new contact in the Nextcloud CardDAV addressbook",
    responses={
        201: {
            "description": "Contact created successfully",
            "model": Contact,
        },
        400: {
            "description": "Invalid contact data",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid contact data provided"}
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
                    "example": {"detail": "Access denied to addressbook"}
                }
            },
        },
        404: {
            "description": "Addressbook not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Addressbook not found"}
                }
            },
        },
        503: {
            "description": "Server error or connection issue",
            "content": {
                "application/json": {
                    "example": {"detail": "Could not create contact: Connection failed"}
                }
            },
        },
    },
    tags=["contacts"],
)
async def create_contact_endpoint(
    contact: Contact,
    credentials: HTTPBasicCredentials = Depends(security)
):
    """
    Create a new contact in the Nextcloud CardDAV addressbook.
    
    Creates a new contact using the CardDAV protocol. The contact data is converted
    to vCard format and stored in the specified Nextcloud addressbook.
    
    **Key Features:**
    - Automatic UID generation if not provided
    - Full vCard format support
    - CardDAV protocol compliance
    - Comprehensive contact information storage
    
    **Authentication:**
    Requires HTTP Basic Authentication with valid Nextcloud credentials.
    
    **Contact Information Supported:**
    - Personal details (name, birthday, notes)
    - Multiple email addresses with type tags
    - Multiple phone numbers with type tags
    - Multiple physical addresses with full details
    - Group/category assignments
    
    **UID Handling:**
    If no UID is provided in the request, a UUID4 will be automatically generated.
    The UID must be unique within the addressbook.
    """
    try:
        if IS_DEBUG:
            print(f"Received contact to create: {contact}")
        
        # Authenticate with Nextcloud
        user_info = authenticate_with_nextcloud(credentials)
        if IS_DEBUG:
            print(f"create_contact_endpoint: user_info: {user_info}")
        
        # Call the create_contact function to create the contact on the server
        created_contact = await create_contact(
            credentials=credentials,
            contact=contact
        )
        
        return created_contact
        
    except Exception as e:
        if IS_DEBUG:
            print(f"Error creating contact: {e}")
        raise HTTPException(status_code=503, detail=f"Could not create contact: {str(e)}")



@router.get(
    "/{uid}",
    operation_id="get_contact_by_uid",
    response_model=Contact,
    summary="Get contact by UID",
    description="Retrieve a single contact by its unique identifier",
    responses={
        200: {
            "description": "Contact retrieved successfully",
            "model": Contact,
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
                    "example": {"detail": "Access denied to addressbook"}
                }
            },
        },
        404: {
            "description": "Contact not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Contact with UID 550e8400-e29b-41d4-a716-446655440000 not found"}
                }
            },
        },
        503: {
            "description": "Server error or connection issue",
            "content": {
                "application/json": {
                    "example": {"detail": "Could not retrieve contact: Connection failed"}
                }
            },
        },
    },
    tags=["contacts"],
)
async def read_contact_endpoint(
    uid: str = Path(
        ...,
        description="Unique identifier for the contact",
        example="550e8400-e29b-41d4-a716-446655440000",
        min_length=1,
        max_length=255,
    ),
    privacy: bool = Query(
        False,
        description="Enable privacy mode to mask sensitive values in the response",
        example=False
    ),
    credentials: HTTPBasicCredentials = Depends(security)
):
    """
    Retrieve a single contact by its UID from the Nextcloud CardDAV addressbook.
    
    Performs a CardDAV GET request to fetch a specific contact using its unique identifier.
    The contact data is retrieved from the Nextcloud server and converted from vCard format
    to a structured Contact object.
    
    **Key Features:**
    - Direct contact retrieval by UID
    - Full contact information including all fields
    - CardDAV protocol compliance
    - Efficient single-contact lookup
    - Optional privacy mode for sensitive data masking
    
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
    
    **Returned Data:**
    Complete contact information including personal details, communication methods,
    addresses, and organizational data as stored in the CardDAV server.
    
    **Note:** When privacy mode is enabled, certain sensitive fields may be masked
    or omitted from the response to protect confidential information.
    """
    try:
        if IS_DEBUG:
            print(f"Retrieving contact with UID: {uid}")
        
        # Authenticate with Nextcloud
        user_info = authenticate_with_nextcloud(credentials)
        if IS_DEBUG:
            print(f"read_contact_endpoint: user_info: {user_info}")
        
        # Call the get_contact_by_uid function to retrieve the contact from the server
        contact = await get_contact_by_uid(
            credentials=credentials,
            uid=uid,
            privacy=privacy
        )
        
        # If contact is not found, raise a 404 error
        if contact is None:
            raise HTTPException(status_code=404, detail=f"Contact with UID {uid} not found")
        
        return contact
        
    except ValueError as e:
        # Handle validation errors
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if IS_DEBUG:
            print(f"Error retrieving contact: {e}")
        raise HTTPException(status_code=503, detail=f"Could not retrieve contact: {str(e)}")



@router.put(
    "/{uid}",
    operation_id="update_contact_by_uid",
    response_model=Contact,
    summary="Update contact by UID",
    description="Update an existing contact in the Nextcloud CardDAV addressbook",
    responses={
        200: {
            "description": "Contact updated successfully",
            "model": Contact,
        },
        400: {
            "description": "Invalid request data or UID mismatch",
            "content": {
                "application/json": {
                    "examples": {
                        "uid_mismatch": {
                            "summary": "UID mismatch",
                            "value": {"detail": "UID in path (123) doesn't match contact UID (456)"}
                        },
                        "invalid_data": {
                            "summary": "Invalid contact data",
                            "value": {"detail": "Invalid contact data provided"}
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
                    "example": {"detail": "Access denied to addressbook"}
                }
            },
        },
        404: {
            "description": "Contact not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Contact with UID 550e8400-e29b-41d4-a716-446655440000 not found"}
                }
            },
        },
        503: {
            "description": "Server error or connection issue",
            "content": {
                "application/json": {
                    "example": {"detail": "Could not update contact: Connection failed"}
                }
            },
        },
    },
    tags=["contacts"],
)
async def update_contact_endpoint(
    contact_update: Contact,
    uid: str = Path(
        ...,
        description="Unique identifier for the contact",
        example="550e8400-e29b-41d4-a716-446655440000",
        min_length=1,
        max_length=255,
    ),
    credentials: HTTPBasicCredentials = Depends(security)
):
    """
    Update an existing contact in the Nextcloud CardDAV addressbook.
    
    Updates an existing contact using the CardDAV protocol. The contact data is converted
    to vCard format and replaces the existing contact on the Nextcloud server.
    
    **Key Features:**
    - Complete contact replacement (not partial updates)
    - UID validation and consistency checking
    - CardDAV protocol compliance
    - Automatic vCard format conversion
    
    **Authentication:**
    Requires HTTP Basic Authentication with valid Nextcloud credentials.
    
    **UID Consistency:**
    The UID in the URL path must match the UID in the request body. This ensures
    data integrity and prevents accidental overwrites.
    
    **Update Behavior:**
    - Replaces the entire contact record
    - Preserves the original UID and vcs_uri
    - Updates all provided fields
    - Maintains CardDAV server timestamps
    
    **URL Resolution:**
    If the contact has a vcs_uri, it will be used for the update. Otherwise,
    the URL is constructed from the addressbook path and contact UID.
    """
    try:
        # Ensure the UID in the path matches the contact's UID
        if contact_update.uid != uid:
            raise HTTPException(
                status_code=400,
                detail=f"UID in path ({uid}) doesn't match contact UID ({contact_update.uid})"
            )
        if IS_DEBUG:
            print(f"Updating contact with UID: {uid}")
        
        # Authenticate with Nextcloud
        user_info = authenticate_with_nextcloud(credentials)
        if IS_DEBUG:
            print(f"update_contact_endpoint: user_info: {user_info}")
        
        # Call the update_contact function to update the contact on the server
        updated_contact = await update_contact(
            credentials=credentials,
            contact=contact_update
        )
        
        return updated_contact
        
    except ValueError as e:
        # Handle validation errors
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if IS_DEBUG:
            print(f"Error updating contact: {e}")
        raise HTTPException(status_code=503, detail=f"Could not update contact: {str(e)}")



@router.delete(
    "/{uid}",
    operation_id="delete_contact_by_uid",
    status_code=204,
    summary="Delete contact by UID",
    description="Delete a contact from the Nextcloud CardDAV addressbook",
    responses={
        204: {
            "description": "Contact deleted successfully",
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
                    "example": {"detail": "Access denied to addressbook"}
                }
            },
        },
        404: {
            "description": "Contact not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Contact with UID 550e8400-e29b-41d4-a716-446655440000 not found"}
                }
            },
        },
        503: {
            "description": "Server error or connection issue",
            "content": {
                "application/json": {
                    "example": {"detail": "Could not delete contact: Connection failed"}
                }
            },
        },
    },
    tags=["contacts"],
)
async def delete_contact_endpoint(
    uid: str = Path(
        ...,
        description="Unique identifier for the contact to delete",
        example="550e8400-e29b-41d4-a716-446655440000",
        min_length=1,
        max_length=255,
    ),
    credentials: HTTPBasicCredentials = Depends(security)
):
    """
    Delete a contact from the Nextcloud CardDAV addressbook.
    
    Permanently removes a contact from the Nextcloud server using the CardDAV protocol.
    This operation cannot be undone.
    
    **Key Features:**
    - Permanent contact deletion
    - CardDAV protocol compliance
    - Atomic operation (all-or-nothing)
    - Immediate server synchronization
    
    **Authentication:**
    Requires HTTP Basic Authentication with valid Nextcloud credentials.
    
    **Deletion Process:**
    1. Validates the provided UID format
    2. Authenticates with the Nextcloud server
    3. Constructs the contact URL from UID
    4. Sends CardDAV DELETE request
    5. Returns 204 No Content on success
    
    **Important Notes:**
    - This operation is irreversible
    - The contact will be removed from all synchronized devices
    - Any references to this contact in other applications may become invalid
    - The UID cannot be reused for new contacts in the same addressbook
    """
    try:
        if IS_DEBUG:
            print(f"Deleting contact with UID: {uid}")
        
        # Authenticate with Nextcloud
        user_info = authenticate_with_nextcloud(credentials)
        if IS_DEBUG:
            print(f"delete_contact_endpoint: user_info: {user_info}")
        
        # Call the delete_contact function to delete the contact from the server
        result = await delete_contact(
            credentials=credentials,
            uid=uid
        )
        
        # Return 204 No Content on successful deletion
        return None
        
    except ValueError as e:
        # Handle validation errors
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if IS_DEBUG:
            print(f"Error deleting contact: {e}")
        raise HTTPException(status_code=503, detail=f"Could not delete contact: {str(e)}")



@router.get(
    "/",
    operation_id="get_all_contacts",
    response_model=Page[Contact],
    summary="Get all contacts",
    description="Retrieve all contacts from the Nextcloud CardDAV addressbook",
    responses={
        200: {
            "description": "Contacts retrieved successfully",
            "model": Page[Contact],
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
                    "example": {"detail": "Access denied to addressbook"}
                }
            },
        },
        404: {
            "description": "Addressbook not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Addressbook not found"}
                }
            },
        },
        503: {
            "description": "Server error or connection issue",
            "content": {
                "application/json": {
                    "example": {"detail": "Could not retrieve contacts from backend"}
                }
            },
        },
    },
    tags=["contacts"],
)
async def get_all_contacts_endpoint(
    privacy: bool = Query(
        False,
        description="Enable privacy mode to mask sensitive values in the response",
        example=False
    ),
    credentials: HTTPBasicCredentials = Depends(security)
) -> Page[Contact]:
    """
    Retrieve all contacts from the Nextcloud CardDAV addressbook.
    
    Performs a CardDAV REPORT request to fetch all contacts from the user's default
    addressbook. Returns live data directly from the Nextcloud server.
    
    **Key Features:**
    - Real-time data retrieval from Nextcloud
    - Complete contact information for all contacts
    - CardDAV protocol compliance
    - Efficient bulk contact fetching
    - Optional privacy mode for sensitive data masking
    
    **Authentication:**
    Requires HTTP Basic Authentication with valid Nextcloud credentials.
    
    **Privacy Parameter:**
    - **privacy**: Optional boolean parameter (default: False)
    - When set to True, masks or hides sensitive values in the response
    - Useful for protecting confidential information in logs or public displays
    
    **Returned Data Structure:**
    Each contact includes comprehensive information:
    - **Personal Details**: UID, full name, birthday, notes
    - **Communication**: Multiple email addresses and phone numbers with type tags
    - **Location**: Multiple physical addresses with complete details
    - **Organization**: Group/category assignments
    - **Metadata**: vCard URI for direct server access
    
    **Performance Considerations:**
    - Fetches all contacts in a single request
    - May return large datasets for addressbooks with many contacts
    - Consider using search endpoints for filtered results
    - Response time depends on addressbook size and network conditions
    
    **Data Freshness:**
    Returns the most current data from the Nextcloud server, including any recent
    changes made through other clients or interfaces.
    
    **Note:** When privacy mode is enabled, certain sensitive fields may be masked
    or omitted from the response to protect confidential information.
    """
    user_info = authenticate_with_nextcloud(credentials)
    if IS_DEBUG:
        print(f"get_all_contacts_endpoint: user_info: {user_info}")
    
    try:
        contacts = await get_all_contacts(
            credentials=credentials,
            privacy=privacy
        )
    except Exception as e:
        # Handle potential errors during the fetch from Nextcloud
        if IS_DEBUG:
            print(f"Error fetching contacts from Nextcloud: {e}")
        raise HTTPException(status_code=503, detail="Could not retrieve contacts from backend")

    return paginate(contacts)



@router.post(
    "/search",
    operation_id="search_contacts_by_params",
    response_model=List[Contact],
    summary="Search contacts",
    description="Search for contacts using specified criteria",
    responses={
        200: {
            "description": "Search completed successfully",
            "model": List[Contact],
        },
        400: {
            "description": "Invalid search criteria",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid search criteria provided"}
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
                    "example": {"detail": "Access denied to addressbook"}
                }
            },
        },
        404: {
            "description": "Addressbook not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Addressbook not found"}
                }
            },
        },
        503: {
            "description": "Server error or connection issue",
            "content": {
                "application/json": {
                    "example": {"detail": "Could not search contacts: Connection failed"}
                }
            },
        },
    },
    tags=["contacts"],
)
async def search_contacts_endpoint(
    search_criteria: ContactSearchCriteria,
    privacy: bool = Query(
        False,
        description="Enable privacy mode to mask sensitive values in the response",
        example=False
    ),
    credentials: HTTPBasicCredentials = Depends(security)
) -> List[Contact]:
    """
    Search for contacts in the Nextcloud CardDAV addressbook using specified criteria.
    
    Performs server-side filtering using CardDAV's advanced search capabilities.
    This approach is efficient even for large addressbooks as filtering occurs
    on the Nextcloud server rather than retrieving all contacts first.
    
    **Key Features:**
    - Server-side filtering for optimal performance
    - Flexible search criteria with multiple field support
    - Case-insensitive partial matching
    - Configurable search logic (AND/OR operations)
    - Optional privacy mode for sensitive data masking
    
    **Authentication:**
    Requires HTTP Basic Authentication with valid Nextcloud credentials.
    
    **Privacy Parameter:**
    - **privacy**: Optional boolean parameter (default: False)
    - When set to True, masks or hides sensitive values in the response
    - Useful for protecting confidential information in logs or public displays
    
    **Search Fields:**
    - **uid**: Contact unique identifier
    - **full_name**: Contact's display name
    - **email**: Any email address associated with the contact
    - **phone**: Any phone number associated with the contact
    - **address**: Any address field (street, city, state, postal code, country)
    - **birthday**: Contact's birthday date
    - **group**: Group or category assignment
    
    **Search Logic:**
    - **anyof** (default): OR logic - matches contacts with ANY specified criteria
    - **allof**: AND logic - matches contacts with ALL specified criteria
    
    **Search Behavior:**
    - All text searches are case-insensitive
    - Partial matching is used for string fields
    - Empty criteria are ignored
    - Returns empty list if no matches found
    
    **Performance Notes:**
    - More efficient than retrieving all contacts and filtering client-side
    - Response time depends on search complexity and addressbook size
    - Consider using specific criteria to narrow results
    
    **Note:** When privacy mode is enabled, certain sensitive fields may be masked
    or omitted from the response to protect confidential information.
    """
    try:
        # Authenticate with Nextcloud
        user_info = authenticate_with_nextcloud(credentials)
        if IS_DEBUG:
            print(f"search_contacts_endpoint: user_info: {user_info}")
        
        contacts = await search_contacts(
            credentials=credentials,
            search_criteria=search_criteria,
            privacy=privacy
        )
    except Exception as e:
        if IS_DEBUG:
            print(f"Error searching contacts from Nextcloud: {e}")
        raise HTTPException(status_code=503, detail=f"Could not search contacts: {str(e)}")

    return contacts
