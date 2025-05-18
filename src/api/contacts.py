# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

from fastapi import APIRouter, HTTPException, Depends
from typing import List

from fastapi.security import HTTPBasicCredentials
from src.common import security

from src.common.sec import authenticate_with_nextcloud
from src.models.contact import Contact, ContactSearchCriteria
from src.nextcloud.contacts import get_all_contacts, search_contacts, create_contact, update_contact, delete_contact, get_contact_by_uid


IS_DEBUG = False

# --- Router Definition ---
# We're using the get_user_settings dependency directly in each endpoint
# instead of applying validate_api_key to all routes
router = APIRouter()

# --- Endpoints ---
# Each endpoint uses the get_user_settings dependency to get the user settings
# directly from the API key provided in the X-API-Key header

@router.post("/", operation_id="create_contact", response_model=Contact)
async def create_contact_endpoint(
    contact: Contact,
    credentials: HTTPBasicCredentials = Depends(security)
):
    """
    Create a new contact in the Nextcloud CardDAV addressbook.
    
    This endpoint creates a new contact in the specified Nextcloud addressbook
    using the CardDAV protocol. It converts the Contact object to a vCard and
    sends it to the server using a PUT request.
    
    If the contact doesn't have a UID, a new UUID will be generated automatically.
    
    Authentication:
        HTTP Basic Authentication with Nextcloud credentials
    
    Returns:
        Contact: The created Contact object with updated information (like UID and vcs_uri)
    
    Raises:
        HTTPException(401): If authentication fails
        HTTPException(403): If authorization is refused
        HTTPException(404): If the addressbook is not found
        HTTPException(503): If there's a server error or connection issue
    
    Example Request:
        POST /contacts/
        Headers:
            Authorization: Basic dXNlcm5hbWU6cGFzc3dvcmQ=
            Content-Type: application/json
        Body:
            {
              "uid": "550e8400-e29b-41d4-a716-446655440000",
              "full_name": "John Doe",
              "emails": [
                {
                  "tag": "work",
                  "email": "john.doe@example.com"
                }
              ],
              "phones": [
                {
                  "tag": "cell",
                  "number": "+1-555-123-4567"
                }
              ],
              "addresses": [
                {
                  "tag": "home",
                  "street": "123 Main St",
                  "city": "Anytown",
                  "state": "CA",
                  "postal_code": "12345",
                  "country": "USA"
                }
              ],
              "birthday": "1980-01-01",
              "notes": "Project manager",
              "groups": ["friends", "work"]
            }
            
    Example Response:
            {
              "uid": "550e8400-e29b-41d4-a716-446655440000",
              "full_name": "John Doe",
              "vcs_uri": "https://nextcloud.example.com/remote.php/dav/addressbooks/users/username/contacts/550e8400-e29b-41d4-a716-446655440000.vcf",
              "emails": [
                {
                  "tag": "work",
                  "email": "john.doe@example.com"
                }
              ],
              "phones": [
                {
                  "tag": "cell",
                  "number": "+1-555-123-4567"
                }
              ],
              "addresses": [
                {
                  "tag": "home",
                  "street": "123 Main St",
                  "city": "Anytown",
                  "state": "CA",
                  "postal_code": "12345",
                  "country": "USA"
                }
              ],
              "birthday": "1980-01-01",
              "notes": "Project manager",
              "groups": ["friends", "work"]
            }
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



@router.get("/{uid}", operation_id="get_contact_by_uid", response_model=Contact)
async def read_contact_endpoint(
    uid: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    """
    Retrieve a single contact by its UID from the Nextcloud CardDAV addressbook.
    
    This endpoint performs a CardDAV GET request to retrieve a specific contact by its UID
    from the specified Nextcloud addressbook. It requires HTTP Basic Authentication with
    Nextcloud credentials.
    
    The contact is identified by its UID, which must be provided in the URL path.
    
    Authentication:
        HTTP Basic Authentication with Nextcloud credentials
    
    Returns:
        Contact: The Contact object if found
    
    Raises:
        HTTPException(401): If authentication fails
        HTTPException(403): If authorization is refused
        HTTPException(404): If the contact is not found
        HTTPException(503): If there's a server error or connection issue
    
    Example Request:
        GET /contacts/550e8400-e29b-41d4-a716-446655440000
        Headers:
            Authorization: Basic dXNlcm5hbWU6cGFzc3dvcmQ=
            
    Example Response:
        {
          "uid": "550e8400-e29b-41d4-a716-446655440000",
          "full_name": "John Doe",
          "vcs_uri": "https://nextcloud.example.com/remote.php/dav/addressbooks/users/username/contacts/550e8400-e29b-41d4-a716-446655440000.vcf",
          "emails": [
            {
              "tag": "work",
              "email": "john.doe@example.com"
            }
          ],
          "phones": [
            {
              "tag": "cell",
              "number": "+1-555-123-4567"
            }
          ],
          "addresses": [
            {
              "tag": "home",
              "street": "123 Main St",
              "city": "Anytown",
              "state": "CA",
              "postal_code": "12345",
              "country": "USA"
            }
          ],
          "birthday": "1980-01-01",
          "notes": "Project manager",
          "groups": ["friends", "work"]
        }
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
            uid=uid
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



@router.put("/{uid}", operation_id="update_contact_by_uid", response_model=Contact)
async def update_contact_endpoint(
    uid: str,
    contact_update: Contact,
    credentials: HTTPBasicCredentials = Depends(security)
):
    """
    Update an existing contact in the Nextcloud CardDAV addressbook.
    
    This endpoint updates an existing contact in the specified Nextcloud addressbook
    using the CardDAV protocol. It converts the Contact object to a vCard and
    sends it to the server using a PUT request.
    
    The contact must have a valid UID that matches the UID in the URL path.
    If the contact has a vcs_uri, it will be used as the update URL. Otherwise,
    the function will construct a URL based on the user's Nextcloud addressbook URL and the contact's UID.
    
    Authentication:
        HTTP Basic Authentication with Nextcloud credentials
    
    Returns:
        Contact: The updated Contact object
    
    Raises:
        HTTPException(400): If the UID in the path doesn't match the contact's UID
        HTTPException(401): If authentication fails
        HTTPException(403): If authorization is refused
        HTTPException(404): If the contact is not found
        HTTPException(503): If there's a server error or connection issue
    
    Example Request:
        PUT /contacts/550e8400-e29b-41d4-a716-446655440000
        Headers:
            Authorization: Basic dXNlcm5hbWU6cGFzc3dvcmQ=
            Content-Type: application/json
        Body:
            {
              "uid": "550e8400-e29b-41d4-a716-446655440000",
              "full_name": "John Doe Updated",
              "emails": [
                {
                  "tag": "work",
                  "email": "john.doe.updated@example.com"
                }
              ],
              "phones": [
                {
                  "tag": "cell",
                  "number": "+1-555-123-4567"
                }
              ],
              "addresses": [
                {
                  "tag": "home",
                  "street": "123 Main St",
                  "city": "Anytown",
                  "state": "CA",
                  "postal_code": "12345",
                  "country": "USA"
                }
              ],
              "birthday": "1980-01-01",
              "notes": "Project manager - updated",
              "groups": ["friends", "work", "vip"]
            }
            
    Example Response:
            {
              "uid": "550e8400-e29b-41d4-a716-446655440000",
              "full_name": "John Doe Updated",
              "vcs_uri": "https://nextcloud.example.com/remote.php/dav/addressbooks/users/username/contacts/550e8400-e29b-41d4-a716-446655440000.vcf",
              "emails": [
                {
                  "tag": "work",
                  "email": "john.doe.updated@example.com"
                }
              ],
              "phones": [
                {
                  "tag": "cell",
                  "number": "+1-555-123-4567"
                }
              ],
              "addresses": [
                {
                  "tag": "home",
                  "street": "123 Main St",
                  "city": "Anytown",
                  "state": "CA",
                  "postal_code": "12345",
                  "country": "USA"
                }
              ],
              "birthday": "1980-01-01",
              "notes": "Project manager - updated",
              "groups": ["friends", "work", "vip"]
            }
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



@router.delete("/{uid}", operation_id="delete_contact_by_uid", status_code=204)
async def delete_contact_endpoint(
    uid: str,
    credentials: HTTPBasicCredentials = Depends(security)
):
    """
    Delete a contact from the Nextcloud CardDAV addressbook.
    
    This endpoint deletes a contact from the specified Nextcloud addressbook
    using the CardDAV protocol. It sends a DELETE request to the server.
    
    The contact is identified by its UID, which must be provided in the URL path.
    
    Authentication:
        HTTP Basic Authentication with Nextcloud credentials
    
    Returns:
        204 No Content on successful deletion
    
    Raises:
        HTTPException(401): If authentication fails
        HTTPException(403): If authorization is refused
        HTTPException(404): If the contact is not found
        HTTPException(503): If there's a server error or connection issue
    
    Example Request:
        DELETE /contacts/550e8400-e29b-41d4-a716-446655440000
        Headers:
            Authorization: Basic dXNlcm5hbWU6cGFzc3dvcmQ=
            
    Example Response:
        HTTP/1.1 204 No Content
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



# This endpoint fetches LIVE data from Nextcloud via get_all_contacts
@router.get("/", operation_id="get_all_contacts", response_model=List[Contact])
async def get_all_contacts_endpoint(
    credentials: HTTPBasicCredentials = Depends(security)
) -> List[Contact]:
    """
    Retrieve all contacts from a Nextcloud CardDAV addressbook.
    
    This endpoint performs a CardDAV REPORT request to retrieve all contacts from
    the specified Nextcloud addressbook. It requires HTTP Basic Authentication with
    Nextcloud credentials.
    
    The endpoint returns a list of Contact objects containing comprehensive contact
    information including:
    - UID
    - Full name
    - Email addresses (with tags like 'home', 'work')
    - Phone numbers (with tags like 'cell', 'home', 'work')
    - Physical addresses (with tags and components like street, city, etc.)
    - Birthday (formatted as YYYY-MM-DD)
    - Notes
    - Groups/categories
    - vCard URI
    
    Authentication:
        HTTP Basic Authentication with Nextcloud credentials
    
    Returns:
        List[Contact]: A list of Contact objects representing all contacts in the addressbook
    
    Raises:
        HTTPException(401): If authentication fails
        HTTPException(403): If authorization is refused
        HTTPException(404): If the addressbook is not found
        HTTPException(503): If there's a server error or connection issue
    
    Example Request:
        GET /contacts/
        Headers:
            Authorization: Basic dXNlcm5hbWU6cGFzc3dvcmQ=
            
    Example Response:
        [
          {
            "uid": "550e8400-e29b-41d4-a716-446655440000",
            "full_name": "John Doe",
            "vcs_uri": "https://nextcloud.example.com/remote.php/dav/addressbooks/users/username/contacts/550e8400-e29b-41d4-a716-446655440000.vcf",
            "emails": [
              {
                "tag": "work",
                "email": "john.doe@example.com"
              }
            ],
            "phones": [
              {
                "tag": "cell",
                "number": "+1-555-123-4567"
              }
            ],
            "addresses": [
              {
                "tag": "home",
                "street": "123 Main St",
                "city": "Anytown",
                "state": "CA",
                "postal_code": "12345",
                "country": "USA"
              }
            ],
            "birthday": "1980-01-01",
            "notes": "Project manager",
            "groups": ["friends", "work"]
          },
          {
            "uid": "550e8400-e29b-41d4-a716-446655440001",
            "full_name": "Jane Smith",
            "vcs_uri": "https://nextcloud.example.com/remote.php/dav/addressbooks/users/username/contacts/550e8400-e29b-41d4-a716-446655440001.vcf",
            "emails": [
              {
                "tag": "personal",
                "email": "jane.smith@example.com"
              }
            ],
            "phones": [
              {
                "tag": "home",
                "number": "+1-555-987-6543"
              }
            ],
            "addresses": [],
            "birthday": null,
            "notes": "Software developer",
            "groups": ["work", "tech"]
          }
        ]
    """
    user_info = authenticate_with_nextcloud(credentials)
    if IS_DEBUG:
        print(f"get_all_contacts_endpoint: user_info: {user_info}")
    
    try:
        contacts = await get_all_contacts(
            credentials=credentials
        )
    except Exception as e:
        # Handle potential errors during the fetch from Nextcloud
        if IS_DEBUG:
            print(f"Error fetching contacts from Nextcloud: {e}")
        raise HTTPException(status_code=503, detail="Could not retrieve contacts from backend")

    return contacts



@router.post("/search", operation_id="search_contacts_by_params", response_model=List[Contact])
async def search_contacts_endpoint(
    search_criteria: ContactSearchCriteria,
    credentials: HTTPBasicCredentials = Depends(security)
) -> List[Contact]:
    """
    Search for contacts in a Nextcloud CardDAV addressbook using specified criteria.
    
    This endpoint performs a CardDAV REPORT request with filters to search for contacts
    matching the specified criteria. The search is performed server-side using CardDAV's
    filtering capabilities, making it efficient even for large addressbooks.
    
    The search criteria are provided as a JSON object in the request body, with fields
    corresponding to the ContactSearchCriteria model. All search fields are optional,
    and case-insensitive partial matching is used for string fields.
    
    Supported search fields include:
    - uid: Search by contact UID
    - full_name: Search by contact's full name
    - email: Search by any email address
    - phone: Search by any phone number
    - address: Search by any address field (street, city, state, etc.)
    - birthday: Search by birthday
    - group: Search by group/category
    
    The search_type parameter controls the search logic:
    - "anyof" (default): Returns contacts that match ANY of the specified criteria (OR logic)
    - "allof": Returns contacts that match ALL of the specified criteria (AND logic)
    
    Authentication:
        HTTP Basic Authentication with Nextcloud credentials
    
    Returns:
        List[Contact]: A list of Contact objects that match the search criteria
    
    Raises:
        HTTPException(401): If authentication fails
        HTTPException(403): If authorization is refused
        HTTPException(404): If the addressbook is not found
        HTTPException(503): If there's a server error or connection issue
    
    Example Request:
        POST /contacts/search
        Headers:
            Authorization: Basic dXNlcm5hbWU6cGFzc3dvcmQ=
            Content-Type: application/json
        Body:
            {
              "full_name": "John",
              "email": "example.com",
              "search_type": "anyof"
            }
        
        This will find contacts with "John" in their name OR "example.com" in their email.
        
    Example Response:
        [
          {
            "uid": "550e8400-e29b-41d4-a716-446655440000",
            "full_name": "John Doe",
            "vcs_uri": "https://nextcloud.example.com/remote.php/dav/addressbooks/users/username/contacts/550e8400-e29b-41d4-a716-446655440000.vcf",
            "emails": [
              {
                "tag": "work",
                "email": "john.doe@example.com"
              }
            ],
            "phones": [
              {
                "tag": "cell",
                "number": "+1-555-123-4567"
              }
            ],
            "addresses": [
              {
                "tag": "home",
                "street": "123 Main St",
                "city": "Anytown",
                "state": "CA",
                "postal_code": "12345",
                "country": "USA"
              }
            ],
            "birthday": "1980-01-01",
            "notes": "Project manager",
            "groups": ["friends", "work"]
          }
        ]
    """
    try:
        # Authenticate with Nextcloud
        user_info = authenticate_with_nextcloud(credentials)
        if IS_DEBUG:
            print(f"search_contacts_endpoint: user_info: {user_info}")
        
        contacts = await search_contacts(
            credentials=credentials,
            search_criteria=search_criteria
        )
    except Exception as e:
        if IS_DEBUG:
            print(f"Error searching contacts from Nextcloud: {e}")
        raise HTTPException(status_code=503, detail=f"Could not search contacts: {str(e)}")

    return contacts
