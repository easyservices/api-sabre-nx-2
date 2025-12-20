# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

from fastapi import APIRouter, HTTPException, Depends, Path, Query, Response
from typing import List

from src.dependencies.auth import authenticated_user, AuthContext
from src.models.contact import Contact, ContactSearchCriteria
from src.nextcloud.contacts import get_all_contacts, search_contacts, create_contact, update_contact, delete_contact, get_contact_by_uid
from fastapi_pagination import Page, paginate
from src import logger
from src.api.responses import CONTACT_ERROR_RESPONSES
from src.common.cache import (
    build_cache_key,
    get_contact_caches,
    invalidate_contact_caches_for_user,
    set_cache_bypass,
    set_cache_headers,
)
from src.common.nextcloud_utils import run_nextcloud_call


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
        **CONTACT_ERROR_RESPONSES,
        404: {
            "description": "Addressbook not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Addressbook not found"}
                }
            },
        },
    },
    tags=["contacts"],
)
async def create_contact_endpoint(
    contact: Contact,
    auth: AuthContext = Depends(authenticated_user)
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
    logger.debug(f"Received contact to create: {contact}")

    created_contact = await run_nextcloud_call(
        "create contact",
        create_contact,
        credentials=auth.credentials,
        contact=contact,
        user_info=auth.user_info,
    )

    invalidate_contact_caches_for_user(auth.credentials.username)
    return created_contact



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
        **CONTACT_ERROR_RESPONSES,
        404: {
            "description": "Contact not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Contact with UID 550e8400-e29b-41d4-a716-446655440000 not found"}
                }
            },
        },
    },
    tags=["contacts"],
)
async def read_contact_endpoint(
    response: Response,
    uid: str = Path(
        ...,
        description="Unique identifier for the contact",
        example="550e8400-e29b-41d4-a716-446655440000",
        min_length=1,
        max_length=255,
    ),
    auth: AuthContext = Depends(authenticated_user),
    privacy: bool = Query(
        False,
        description="Enable privacy mode to mask sensitive values in the response",
        example=False
    ),
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
    logger.debug(f"Retrieving contact with UID: {uid} with privacy mode: {privacy}")
    caches = get_contact_caches()
    cache_key = build_cache_key(auth.credentials.username, "contact", uid, str(privacy))
    if cache_key in caches.by_uid:
        set_cache_headers(response, caches.by_uid, cache_key, hit=True)
        return caches.by_uid[cache_key]

    contact = await run_nextcloud_call(
        "retrieve contact",
        get_contact_by_uid,
        credentials=auth.credentials,
        uid=uid,
        privacy=privacy,
        user_info=auth.user_info,
    )

    if contact is None:
        res_txt = f"Contact with UID {uid} not found"
        logger.error(res_txt)
        raise HTTPException(status_code=404, detail=res_txt)

    caches.by_uid[cache_key] = contact
    set_cache_headers(response, caches.by_uid, cache_key, hit=False)
    return contact



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
        **CONTACT_ERROR_RESPONSES,
        404: {
            "description": "Contact not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Contact with UID 550e8400-e29b-41d4-a716-446655440000 not found"}
                }
            },
        },
    },
    tags=["contacts"],
)
async def update_contact_endpoint(
    response: Response,
    contact_update: Contact,
    uid: str = Path(
        ...,
        description="Unique identifier for the contact",
        example="550e8400-e29b-41d4-a716-446655440000",
        min_length=1,
        max_length=255,
    ),
    auth: AuthContext = Depends(authenticated_user)
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
    - Preserves the original UID and url
    - Updates all provided fields
    - Maintains CardDAV server timestamps
    
    **URL Resolution:**
    If the contact has a url, it will be used for the update. Otherwise,
    the URL is constructed from the addressbook path and contact UID.
    """
    logger.debug(f"Updating contact with UID: {uid}")

    # Ensure the UID in the path matches the contact's UID
    if contact_update.uid != uid:
        res_txt = f"UID in path ({uid}) doesn't match contact UID ({contact_update.uid})"
        logger.error(res_txt)
        raise HTTPException(
            status_code=400,
            detail=res_txt
        )
    logger.debug(f"Updating contact with UID: {uid}")
    
    updated_contact = await run_nextcloud_call(
        "update contact",
        update_contact,
        credentials=auth.credentials,
        contact=contact_update,
        user_info=auth.user_info,
    )

    invalidate_contact_caches_for_user(auth.credentials.username)
    set_cache_bypass(response)
    return updated_contact



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
        **CONTACT_ERROR_RESPONSES,
        404: {
            "description": "Contact not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Contact with UID 550e8400-e29b-41d4-a716-446655440000 not found"}
                }
            },
        },
    },
    tags=["contacts"],
)
async def delete_contact_endpoint(
    response: Response,
    uid: str = Path(
        ...,
        description="Unique identifier for the contact to delete",
        example="550e8400-e29b-41d4-a716-446655440000",
        min_length=1,
        max_length=255,
    ),
    auth: AuthContext = Depends(authenticated_user)
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
    logger.debug(f"Deleting contact with UID: {uid}")
    
    await run_nextcloud_call(
        "delete contact",
        delete_contact,
        credentials=auth.credentials,
        uid=uid,
        user_info=auth.user_info,
    )
    
    invalidate_contact_caches_for_user(auth.credentials.username)
    set_cache_bypass(response)
    return None



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
        **CONTACT_ERROR_RESPONSES,
        404: {
            "description": "Addressbook not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Addressbook not found"}
                }
            },
        },
    },
    tags=["contacts"],
)
async def get_all_contacts_endpoint(
    response: Response,
    auth: AuthContext = Depends(authenticated_user),
    privacy: bool = Query(
        False,
        description="Enable privacy mode to mask sensitive values in the response",
        example=False
    ),
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
    - **Metadata**: vCard URL for direct server access
    
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
    logger.debug(f"Get all contacts with privacy mode: {privacy}")

    caches = get_contact_caches()
    cache_key = build_cache_key(auth.credentials.username, "contacts_all", str(privacy))
    if cache_key in caches.list_all:
        set_cache_headers(response, caches.list_all, cache_key, hit=True)
        return paginate(caches.list_all[cache_key])

    contacts = await run_nextcloud_call(
        "get all contacts",
        get_all_contacts,
        credentials=auth.credentials,
        privacy=privacy,
        user_info=auth.user_info,
    )

    caches.list_all[cache_key] = contacts
    set_cache_headers(response, caches.list_all, cache_key, hit=False)

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
        **CONTACT_ERROR_RESPONSES,
        404: {
            "description": "Addressbook not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Addressbook not found"}
                }
            },
        },
    },
    tags=["contacts"],
)
async def search_contacts_endpoint(
    response: Response,
    search_criteria: ContactSearchCriteria,
    privacy: bool = Query(
        False,
        description="Enable privacy mode to mask sensitive values in the response",
        example=False
    ),
    auth: AuthContext = Depends(authenticated_user)
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
    logger.debug(f"Get contacts using search criterias: {search_criteria} with privacy mode: {privacy}")

    caches = get_contact_caches()
    cache_key = build_cache_key(auth.credentials.username, "contacts_search", search_criteria.json(), str(privacy))
    if cache_key in caches.search:
        set_cache_headers(response, caches.search, cache_key, hit=True)
        return caches.search[cache_key]

    contacts = await run_nextcloud_call(
        "search contacts",
        search_contacts,
        credentials=auth.credentials,
        search_criteria=search_criteria,
        privacy=privacy,
        user_info=auth.user_info,
    )

    caches.search[cache_key] = contacts
    set_cache_headers(response, caches.search, cache_key, hit=False)
    return contacts
