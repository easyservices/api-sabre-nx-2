# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Nextcloud CardDAV Contacts Integration Module

This module provides comprehensive CardDAV protocol implementation for managing
contacts in Nextcloud servers. It handles all CRUD operations, search functionality,
and vCard format conversion for seamless contact management.

**CardDAV Protocol Implementation:**
- **RFC 6352 Compliance**: Full CardDAV specification support
- **vCard Processing**: Automatic conversion between JSON and vCard formats
- **WebDAV Operations**: REPORT, GET, PUT, DELETE request handling
- **Server Communication**: Asynchronous HTTP operations with proper error handling

**Key Features:**
- **Contact Retrieval**: Get all contacts or specific contacts by UID
- **Contact Search**: Advanced server-side filtering with multiple criteria
- **Contact Management**: Create, update, and delete operations
- **Format Conversion**: Seamless vCard ↔ JSON transformation
- **Error Handling**: Comprehensive exception management with proper HTTP status codes

**Supported Operations:**
- `get_all_contacts()`: Bulk contact retrieval from addressbook
- `get_contact_by_uid()`: Single contact lookup by unique identifier
- `search_contacts()`: Advanced filtering with multiple search criteria
- `create_contact()`: New contact creation with automatic UID generation
- `update_contact()`: Existing contact modification with conflict detection
- `delete_contact()`: Contact removal with proper cleanup

**vCard Support:**
- **Standard Fields**: Name, email, phone, address, birthday, notes
- **Extended Properties**: Groups, categories, custom fields
- **Multiple Values**: Support for multiple emails, phones, addresses
- **Type Tags**: Proper handling of field types (home, work, cell, etc.)

**Authentication & Security:**
- HTTP Basic Authentication with Nextcloud credentials
- Secure credential handling and validation
- Proper authorization checking for addressbook access

**Performance Optimizations:**
- Asynchronous operations for non-blocking I/O
- Efficient XML parsing and generation
- Minimal data transfer with targeted queries
- Connection pooling for HTTP requests

**Error Handling:**
Comprehensive error management with appropriate HTTP status codes:
- 400: Invalid request data or parameters
- 401: Authentication failures
- 403: Authorization/permission issues
- 404: Contact or addressbook not found
- 503: Server communication errors
"""

from fastapi import HTTPException
from src.common.libs.helpers import gen_nxtcloud_url_addressbook
from fastapi.security import HTTPBasicCredentials
from src.common.sec import authenticate_with_nextcloud, gen_basic_auth_header
from src.models.contact import Contact, ContactSearchCriteria
from typing import List, Dict, Optional
import aiohttp

from src.nextcloud import API_ERR_CONNECTION_ERROR
from src.nextcloud.libs.carddav_helpers import (
    create_request_headers,
    create_request_xml,
    create_search_request_xml,
    handle_response_status,
    parse_xml_response,
    parse_vcard_to_contact,
    contact_to_vcard,
    create_vcard_headers
)

IS_DEBUG = False  # Set to True for debugging - be aware of sensitive data in logs


async def get_all_contacts(credentials: HTTPBasicCredentials, addressbook_name: Optional[str] = None, privacy: Optional[bool] = False) -> List[Contact]:
    """
    Retrieve all contacts from the specified Nextcloud CardDAV addressbook.
    
    This function performs a CardDAV REPORT request to retrieve all contacts from
    the specified Nextcloud addressbook. It handles the HTTP request, parses the
    XML response, and converts the vCard data into Contact objects.
    
    The Contact objects include the following information:
    - UID
    - Full name
    - Email addresses
    - Phone numbers
    - Physical addresses
    - Birthday (formatted as YYYY-MM-DD)
    - Notes
    - Groups/categories
    - vCard URI

    Args:
        credentials (HTTPBasicCredentials): HTTP Basic Authentication credentials.
        addressbook_name (Optional[str]): The name of the addressbook. Defaults to None (uses "contacts").
        privacy (Optional[bool]): Enable privacy mode to mask sensitive values. Defaults to False.

    Returns:
        List[Contact]: List of Contact objects parsed from vCard data.

    Raises:
        HTTPException: For authentication, authorization, server, or parsing errors.
    """
    if IS_DEBUG:
        print(f"get_all_contacts: credentials: {credentials}")
        
    user_info = authenticate_with_nextcloud(credentials)
    if IS_DEBUG:
        print(f"get_all_contacts: User info: {user_info}")
    
    carddav_url = gen_nxtcloud_url_addressbook(user_info['id'], addressbook_name)
    if IS_DEBUG:
        print(f"get_all_contacts: carddav_url: {carddav_url}")

    auth_header = gen_basic_auth_header(credentials.username, credentials.password)
    headers = create_request_headers(auth_header)
    if IS_DEBUG:
        print(f"get_all_contacts: headers: {headers}")

    xml_data = create_request_xml()
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.request("REPORT", carddav_url, headers=headers, data=xml_data) as response:
                status_code = response.status
                response_text = await response.text()
                
                # Handle response status
                handle_response_status(status_code, response_text)
                
                # Parse XML response
                parsed_data = parse_xml_response(response_text)
                
                # Parse vCards to Contact objects
                contacts = []
                for i, item in enumerate(parsed_data):
                    try:
                        contact = parse_vcard_to_contact(item['vcard_data'], item['href'], privacy)
                        if contact:
                            contacts.append(contact)
                        else:
                            print(f"Warning: Failed to parse contact #{i+1} at href: {item.get('href', 'Unknown')}")
                    except Exception as e:
                        print(f"Error parsing contact #{i+1}: {e}")
                        print(f"Contact href: {item.get('href', 'Unknown')}")
                        print(f"vCard data (first 200 chars): {item.get('vcard_data', '')[:200]}")
                        # Continue processing other contacts instead of failing completely
                        continue
                
                return contacts
                
        except aiohttp.ClientError as e:
            raise HTTPException(status_code=500, detail=f"{API_ERR_CONNECTION_ERROR}: {str(e)}")


async def search_contacts(
    credentials: HTTPBasicCredentials,
    search_criteria: ContactSearchCriteria,
    addressbook_name: Optional[str] = None,
    privacy: Optional[bool] = False
) -> List[Contact]:
    """
    Search for contacts from the specified Nextcloud CardDAV addressbook based on search criteria.
    
    This function performs a CardDAV REPORT request with filters to search for contacts
    matching the specified criteria. The search is performed server-side using CardDAV's
    filtering capabilities.
    
    Args:
        credentials (HTTPBasicCredentials): HTTP Basic Authentication credentials.
        search_criteria (ContactSearchCriteria): Pydantic model containing search criteria.
            All fields are optional and case-insensitive partial matches are used for string fields.
        addressbook_name (Optional[str]): The name of the addressbook. Defaults to None (uses "contacts").
        privacy (Optional[bool]): Enable privacy mode to mask sensitive values. Defaults to False.
    
    Returns:
        List[Contact]: List of Contact objects that match the search criteria.
    
    Raises:
        HTTPException: For authentication, authorization, server, or parsing errors.
    """
    if IS_DEBUG:
        print(f"search_contacts: credentials: {credentials}")
        
    user_info = authenticate_with_nextcloud(credentials)
    if IS_DEBUG:
        print(f"search_contacts: User info: {user_info}")
    
    carddav_url = gen_nxtcloud_url_addressbook(user_info['id'], addressbook_name)
    if IS_DEBUG:
        print(f"search_contacts: carddav_url: {carddav_url}")
    
    auth_header = gen_basic_auth_header(credentials.username, credentials.password)
    # Extract search_type from the criteria
    search_type = search_criteria.search_type
    
    # Convert the Pydantic model to a dictionary for the XML creation
    criteria_dict = search_criteria.to_dict()
    
    # Create the XML request with search filters
    xml_data = create_search_request_xml(criteria_dict, search_type)
    
    # Create request headers
    headers = create_request_headers(auth_header)
    
    # Send the request and process the response
    async with aiohttp.ClientSession() as session:
        try:
            async with session.request("REPORT", carddav_url, headers=headers, data=xml_data) as response:
                status_code = response.status
                response_text = await response.text()
                
                # Handle response status
                handle_response_status(status_code, response_text)
                
                # Parse XML response
                parsed_data = parse_xml_response(response_text)
                
                # Parse vCards to Contact objects
                contacts = []
                for i, item in enumerate(parsed_data):
                    try:
                        contact = parse_vcard_to_contact(item['vcard_data'], item['href'], privacy)
                        if contact:
                            contacts.append(contact)
                        else:
                            print(f"Warning: Failed to parse contact #{i+1} at href: {item.get('href', 'Unknown')}")
                    except Exception as e:
                        print(f"Error parsing contact #{i+1}: {e}")
                        print(f"Contact href: {item.get('href', 'Unknown')}")
                        print(f"vCard data (first 200 chars): {item.get('vCard_data', '')[:200]}")
                        # Continue processing other contacts instead of failing completely
                        continue
                
                return contacts
                
        except aiohttp.ClientError as e:
            raise HTTPException(status_code=500, detail=f"{API_ERR_CONNECTION_ERROR}: {str(e)}")


async def create_contact(credentials: HTTPBasicCredentials, contact: Contact, addressbook_name: Optional[str] = None) -> Contact:
    """
    Create a new contact in the specified Nextcloud CardDAV addressbook.
    
    This function performs a CardDAV PUT request to create a new contact in the
    specified Nextcloud addressbook. It converts the Contact object to a vCard
    using the vobject library and sends it to the server.
    
    If the contact doesn't have a UID, a new UUID will be generated.
    
    Args:
        credentials (HTTPBasicCredentials): HTTP Basic Authentication credentials.
        contact (Contact): The Contact object to create.
        addressbook_name (Optional[str]): The name of the addressbook. Defaults to None (uses "contacts").
        
    Returns:
        Contact: The created Contact object with updated information (like UID and vcs_uri).
        
    Raises:
        HTTPException: For authentication, authorization, server, or parsing errors.
    """
    if IS_DEBUG:
        print(f"create_contact: credentials: {credentials}")
        
    user_info = authenticate_with_nextcloud(credentials)
    if IS_DEBUG:
        print(f"create_contact: User info: {user_info}")
    
    # Ensure the contact has a UID
    if not contact.uid:
        contact.uid = Contact.generate_uid()
    
    # Create the URL for the new contact
    # For Nextcloud/Sabre, we need to ensure we're creating the contact in the correct location
    # The URL should typically be the addressbook URL + the contact's UID + .vcf
    # Make sure to handle URL joining properly
    
    # Ensure the carddav_url ends with a slash
    carddav_url = gen_nxtcloud_url_addressbook(user_info['id'], addressbook_name)
    if IS_DEBUG:
        print(f"create_contact: carddav_url: {carddav_url}")
    base_url = carddav_url if carddav_url.endswith('/') else f"{carddav_url}/"
    
    # Create the contact filename with the UID
    contact_filename = f"{contact.uid}.vcf"
    
    # Join the URL properly
    contact_url = f"{base_url}{contact_filename}"
    
    # Update the contact's vcs_uri with the URL where it will be created
    contact.vcs_uri = contact_url

    if IS_DEBUG:
        print(f"Creating contact at URL: {contact_url}")
    
    # Generate the vCard data with the updated vcs_uri
    vcard_data = contact_to_vcard(contact)
    
    # Create headers for the PUT request
    headers = create_vcard_headers(gen_basic_auth_header(credentials.username, credentials.password))
    
    # Send the PUT request
    async with aiohttp.ClientSession() as session:
        try:
            async with session.put(contact_url, headers=headers, data=vcard_data) as response:
                status_code = response.status
                response_text = await response.text()
                
                # Check for success (201 Created or 204 No Content)
                if status_code not in (201, 204):
                    # Special handling for 405 Method Not Allowed
                    if status_code == 405:
                        # This often happens when trying to create a contact in the wrong location
                        error_message = f"Cannot create contact at this URL. The server responded: {response_text}"
                        raise HTTPException(status_code=405, detail=error_message)
                    else:
                        # Handle other error responses
                        handle_response_status(status_code, response_text)
                               
                return contact
                
        except aiohttp.ClientError as e:
            raise HTTPException(status_code=500, detail=f"{API_ERR_CONNECTION_ERROR}: {str(e)}")


async def update_contact(credentials: HTTPBasicCredentials, contact: Contact, addressbook_name: Optional[str] = None) -> Contact:
    """
    Update an existing contact in the specified Nextcloud CardDAV addressbook.
    
    This function performs a CardDAV PUT request to update an existing contact in the
    specified Nextcloud addressbook. It converts the Contact object to a vCard
    using the vobject library and sends it to the server.
    
    The contact must have a valid UID. If vcs_uri is provided, it will be used as the
    update URL. Otherwise, the function will construct a URL based on the carddav_url
    and the contact's UID.
    
    Args:
        credentials (HTTPBasicCredentials): HTTP Basic Authentication credentials.
        contact (Contact): The Contact object to update.
        addressbook_name (Optional[str]): The name of the addressbook. Defaults to None (uses "contacts").
        
    Returns:
        Contact: The updated Contact object.
        
    Raises:
        HTTPException: For authentication, authorization, server, or parsing errors.
        ValueError: If the contact doesn't have a UID.
    """
    if IS_DEBUG:
        print(f"update_contact: credentials: {credentials}")
        
    user_info = authenticate_with_nextcloud(credentials)
    if IS_DEBUG:
        print(f"update_contact: User info: {user_info}")
    
    carddav_url = gen_nxtcloud_url_addressbook(user_info['id'], addressbook_name)
    if IS_DEBUG:
        print(f"update_contact: carddav_url: {carddav_url}")
    
    auth_header = gen_basic_auth_header(credentials.username, credentials.password)
    # Ensure the contact has a UID
    if not contact.uid:
        raise ValueError("Contact must have a UID to be updated")
    
    # Determine the URL to use for the update
    if contact.vcs_uri:
        # Use the existing vcs_uri if available
        contact_url = contact.vcs_uri
    else:
        # Construct a URL based on the carddav_url and UID
        base_url = carddav_url if carddav_url.endswith('/') else f"{carddav_url}/"
        contact_filename = f"{contact.uid}.vcf"
        contact_url = f"{base_url}{contact_filename}"
        
        # Update the contact's vcs_uri if it wasn't already set
        contact.vcs_uri = contact_url

    if IS_DEBUG:
        print(f"updating contact at URL: {contact_url}")
    
    # Generate the vCard data with the updated vcs_uri
    vcard_data = contact_to_vcard(contact)
    
    # Create headers for the PUT request
    headers = create_vcard_headers(auth_header)
    
    # Send the PUT request
    async with aiohttp.ClientSession() as session:
        try:
            async with session.put(contact_url, headers=headers, data=vcard_data) as response:
                status_code = response.status
                response_text = await response.text()
                
                # Check for success (200 OK, 201 Created, or 204 No Content)
                if status_code not in (200, 201, 204):
                    # Special handling for 404 Not Found
                    if status_code == 404:
                        error_message = f"Contact not found at {contact_url}. The server responded: {response_text}"
                        raise HTTPException(status_code=404, detail=error_message)
                    # Special handling for 405 Method Not Allowed
                    elif status_code == 405:
                        error_message = f"Cannot update contact at this URL. The server responded: {response_text}"
                        raise HTTPException(status_code=405, detail=error_message)
                    else:
                        # Handle other error responses
                        handle_response_status(status_code, response_text)
                
                return contact
                
        except aiohttp.ClientError as e:
            raise HTTPException(status_code=500, detail=f"{API_ERR_CONNECTION_ERROR}: {str(e)}")


async def delete_contact(credentials: HTTPBasicCredentials, uid: str, addressbook_name: Optional[str] = None) -> Dict[str, str]:
    """
    Delete a contact from the specified Nextcloud CardDAV addressbook.
    
    This function performs a CardDAV DELETE request to remove a contact from the
    specified Nextcloud addressbook. It requires the UID of the contact to be deleted.
    
    Args:
        credentials (HTTPBasicCredentials): HTTP Basic Authentication credentials.
        uid (str): The UID of the contact to delete.
        addressbook_name (Optional[str]): The name of the addressbook. Defaults to None (uses "contacts").
        
    Returns:
        Dict[str, str]: A dictionary with a success message.
        
    Raises:
        HTTPException: For authentication, authorization, server, or parsing errors.
        ValueError: If the uid is empty or None.
    """
    if IS_DEBUG:
        print(f"delete_contact: credentials: {credentials}")
        
    user_info = authenticate_with_nextcloud(credentials)
    if IS_DEBUG:
        print(f"delete_contact: User info: {user_info}")
    
    carddav_url = gen_nxtcloud_url_addressbook(user_info['id'], addressbook_name)
    if IS_DEBUG:
        print(f"delete_contact: carddav_url: {carddav_url}")
    
    auth_header = gen_basic_auth_header(credentials.username, credentials.password)
    # Validate the UID
    if not uid:
        raise ValueError("Contact UID must be provided for deletion")
    
    # Construct the URL for the contact
    base_url = carddav_url if carddav_url.endswith('/') else f"{carddav_url}/"
    contact_filename = f"{uid}.vcf"
    contact_url = f"{base_url}{contact_filename}"
    
    if IS_DEBUG:
        print(f"Deleting contact at URL: {contact_url}")
    
    # Create headers for the DELETE request
    headers = {
        "authorization": auth_header
    }
    
    # Send the DELETE request
    async with aiohttp.ClientSession() as session:
        try:
            async with session.delete(contact_url, headers=headers) as response:
                status_code = response.status
                response_text = await response.text()
                
                # Check for success (200 OK or 204 No Content)
                if status_code not in (200, 204):
                    # Special handling for 404 Not Found
                    if status_code == 404:
                        error_message = f"Contact not found at {contact_url}. The server responded: {response_text}"
                        raise HTTPException(status_code=404, detail=error_message)
                    # Special handling for 405 Method Not Allowed
                    elif status_code == 405:
                        error_message = f"Cannot delete contact at this URL. The server responded: {response_text}"
                        raise HTTPException(status_code=405, detail=error_message)
                    else:
                        # Handle other error responses
                        handle_response_status(status_code, response_text)
                
                return {"message": f"Contact with UID {uid} successfully deleted"}
                
        except aiohttp.ClientError as e:
            raise HTTPException(status_code=500, detail=f"{API_ERR_CONNECTION_ERROR}: {str(e)}")


async def get_contact_by_uid(credentials: HTTPBasicCredentials, uid: str, addressbook_name: Optional[str] = None, privacy: Optional[bool] = False) -> Optional[Contact]:
    """
    Retrieve a single contact by its UID from the specified Nextcloud CardDAV addressbook.
    
    This function performs a CardDAV GET request to retrieve a specific contact by its UID
    from the specified Nextcloud addressbook. It handles the HTTP request, parses the
    vCard data, and converts it into a Contact object.
    
    Args:
        credentials (HTTPBasicCredentials): HTTP Basic Authentication credentials.
        uid (str): The UID of the contact to retrieve.
        addressbook_name (Optional[str]): The name of the addressbook. Defaults to None (uses "contacts").
        privacy (Optional[bool]): Enable privacy mode to mask sensitive values. Defaults to False.
        
    Returns:
        Optional[Contact]: The Contact object if found, None otherwise.
        
    Raises:
        HTTPException: For authentication, authorization, server, or parsing errors.
        ValueError: If the uid is empty or None.
    """
    if IS_DEBUG:
        print(f"get_contact_by_uid: credentials: {credentials}")
        
    user_info = authenticate_with_nextcloud(credentials)
    if IS_DEBUG:
        print(f"get_contact_by_uid: User info: {user_info}")
    
    carddav_url = gen_nxtcloud_url_addressbook(user_info['id'], addressbook_name)
    if IS_DEBUG:
        print(f"get_contact_by_uid: carddav_url: {carddav_url}")
    
    auth_header = gen_basic_auth_header(credentials.username, credentials.password)
    # Validate the UID
    if not uid:
        raise ValueError("Contact UID must be provided for retrieval")
    
    # Construct the URL for the contact
    base_url = carddav_url if carddav_url.endswith('/') else f"{carddav_url}/"
    contact_filename = f"{uid}.vcf"
    contact_url = f"{base_url}{contact_filename}"
    
    if IS_DEBUG:
        print(f"Retrieving contact at URL: {contact_url}")
    
    # Create headers for the GET request
    headers = {
        "authorization": auth_header
    }
    
    # Send the GET request
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(contact_url, headers=headers) as response:
                status_code = response.status
                
                # If contact not found, return None instead of raising an exception
                if status_code == 404:
                    return None
                
                response_text = await response.text()
                
                # Handle other error responses
                if status_code != 200:
                    handle_response_status(status_code, response_text)
                
                # Parse vCard data to Contact object
                contact = parse_vcard_to_contact(response_text, contact_url, privacy)
                return contact
                
        except aiohttp.ClientError as e:
            raise HTTPException(status_code=500, detail=f"{API_ERR_CONNECTION_ERROR}: {str(e)}")
