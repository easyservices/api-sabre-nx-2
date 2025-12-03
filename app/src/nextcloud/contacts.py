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

from src.common.libs.helpers import gen_nxtcloud_url_addressbook
from fastapi.security import HTTPBasicCredentials
from src.common.sec import authenticate_with_nextcloud, gen_basic_auth_header
from src.models.contact import Contact, ContactSearchCriteria
from typing import List, Dict, Optional

from src.nextcloud.libs.carddav_helpers import (
    parse_xml_response,
    parse_vcard_to_contact,
    contact_to_vcard,
    validate_and_correct_url,
    parse_contacts_from_response
)
from src.nextcloud.libs.dav_clients import CardDavClient
from src import logger


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
    - vCard URL

    Args:
        credentials (HTTPBasicCredentials): HTTP Basic Authentication credentials.
        addressbook_name (Optional[str]): The name of the addressbook. Defaults to None (uses "contacts").
        privacy (Optional[bool]): Enable privacy mode to mask sensitive values. Defaults to False.

    Returns:
        List[Contact]: List of Contact objects parsed from vCard data.

    Raises:
        HTTPException: For authentication, authorization, server, or parsing errors.
    """
    logger.debug(f"get_all_contacts: retrieving all contacts with privacy mode: {privacy}")
        
    user_info = authenticate_with_nextcloud(credentials)
    logger.debug(f"User credentials: {user_info}")
    
    carddav_url = gen_nxtcloud_url_addressbook(user_info['id'], addressbook_name)
    logger.debug(f"get_all_contacts: carddav_url: {carddav_url}")

    auth_header = gen_basic_auth_header(credentials.username, credentials.password)
    client = CardDavClient(carddav_url, auth_header)
    response_text = await client.report_addressbook()

    parsed_data = parse_xml_response(response_text)
    contacts = parse_contacts_from_response(parsed_data, privacy)
    return contacts


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
    logger.debug(f"search_contacts: searching contacts with criteria: {search_criteria} with privacy mode: {privacy}")
        
    user_info = authenticate_with_nextcloud(credentials)
    logger.debug(f"User credentials: {user_info}")
    
    carddav_url = gen_nxtcloud_url_addressbook(user_info['id'], addressbook_name)
    logger.debug(f"search_contacts: carddav_url: {carddav_url}")
    
    auth_header = gen_basic_auth_header(credentials.username, credentials.password)
    # Extract search_type from the criteria
    search_type = search_criteria.search_type
    
    # Convert the Pydantic model to a dictionary for the XML creation
    criteria_dict = search_criteria.to_dict()
    
    client = CardDavClient(carddav_url, auth_header)
    response_text = await client.search_addressbook(criteria_dict, search_type)
    
    # Parse XML response
    parsed_data = parse_xml_response(response_text)
    
    # Parse vCards to Contact objects using the shared helper function
    contacts = parse_contacts_from_response(parsed_data, privacy)
    
    return contacts


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
        Contact: The created Contact object with updated information (like UID and url).
        
    Raises:
        HTTPException: For authentication, authorization, server, or parsing errors.
    """
    logger.debug(f"create_contact: received contact to create: {contact}")
        
    user_info = authenticate_with_nextcloud(credentials)
    logger.debug(f"User credentials: {user_info}")
    
    # Ensure the contact has a UID
    if not contact.uid:
        contact.uid = Contact.generate_uid()
    
    # Create the URL for the new contact
    # For Nextcloud/Sabre, we need to ensure we're creating the contact in the correct location
    # The URL should typically be the addressbook URL + the contact's UID + .vcf
    # Make sure to handle URL joining properly
    
    # Ensure the carddav_url ends with a slash
    carddav_url = gen_nxtcloud_url_addressbook(user_info['id'], addressbook_name)
    logger.debug(f"create_contact: carddav_url: {carddav_url}")
    auth_header = gen_basic_auth_header(credentials.username, credentials.password)
    client = CardDavClient(carddav_url, auth_header)
    
    # Create the contact filename with the UID
    contact_filename = f"{contact.uid}.vcf"
    
    # Join the URL properly
    contact_url = client.build_url(contact_filename)
    
    # Update the contact's url with the URL where it will be created (with validation)
    contact.url = validate_and_correct_url(contact_url)

    logger.debug(f"Creating contact at URL: {contact_url}")
    
    # Generate the vCard data with the updated url
    vcard_data = contact_to_vcard(contact)
    
    await client.create_contact(contact_url, vcard_data)
    return contact


async def update_contact(credentials: HTTPBasicCredentials, contact: Contact, addressbook_name: Optional[str] = None) -> Contact:
    """
    Update an existing contact in the specified Nextcloud CardDAV addressbook.
    
    This function performs a CardDAV PUT request to update an existing contact in the
    specified Nextcloud addressbook. It converts the Contact object to a vCard
    using the vobject library and sends it to the server.
    
    The contact must have a valid UID. If url is provided, it will be used as the
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
    logger.debug(f"update_contact: updating contact with UID: {contact.uid}")
        
    user_info = authenticate_with_nextcloud(credentials)
    logger.debug(f"User credentials: {user_info}")
    
    carddav_url = gen_nxtcloud_url_addressbook(user_info['id'], addressbook_name)
    logger.debug(f"update_contact: carddav_url: {carddav_url}")
    
    auth_header = gen_basic_auth_header(credentials.username, credentials.password)
    client = CardDavClient(carddav_url, auth_header)
    # Ensure the contact has a UID
    if not contact.uid:
        raise ValueError("Contact must have a UID to be updated")
    
    # Determine the URL to use for the update
    if contact.url:
        # Use the existing url if available
        contact_url = contact.url
    else:
        # Construct a URL based on the carddav_url and UID
        contact_filename = f"{contact.uid}.vcf"
        contact_url = client.build_url(contact_filename)
        
        # Update the contact's url if it wasn't already set (with validation)
        contact.url = validate_and_correct_url(contact_url)

    logger.debug(f"updating contact at URL: {contact_url}")
    
    # Generate the vCard data with the updated url
    vcard_data = contact_to_vcard(contact)
    
    await client.update_contact(contact_url, vcard_data)
    return contact


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
    logger.debug(f"delete_contact: deleting contact with UID: {uid}")
        
    user_info = authenticate_with_nextcloud(credentials)
    logger.debug(f"User credentials: {user_info}")
    
    carddav_url = gen_nxtcloud_url_addressbook(user_info['id'], addressbook_name)
    logger.debug(f"delete_contact: carddav_url: {carddav_url}")
    
    auth_header = gen_basic_auth_header(credentials.username, credentials.password)
    client = CardDavClient(carddav_url, auth_header)
    # Validate the UID
    if not uid:
        raise ValueError("Contact UID must be provided for deletion")
    
    # Construct the URL for the contact
    contact_filename = f"{uid}.vcf"
    contact_url = client.build_url(contact_filename)
    
    logger.debug(f"Deleting contact at URL: {contact_url}")
    
    await client.delete_contact(contact_url)
    return {"message": f"Contact with UID {uid} successfully deleted"}


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
    logger.debug(f"get_contact_by_uid: retrieving contact with UID: {uid} with privacy mode: {privacy}")
        
    user_info = authenticate_with_nextcloud(credentials)
    logger.debug(f"User credentials: {user_info}")
    
    carddav_url = gen_nxtcloud_url_addressbook(user_info['id'], addressbook_name)
    logger.debug(f"get_contact_by_uid: carddav_url: {carddav_url}")
    
    auth_header = gen_basic_auth_header(credentials.username, credentials.password)
    client = CardDavClient(carddav_url, auth_header)
    # Validate the UID
    if not uid:
        raise ValueError("Contact UID must be provided for retrieval")
    
    # Construct the URL for the contact
    contact_filename = f"{uid}.vcf"
    contact_url = client.build_url(contact_filename)
    
    logger.debug(f"Retrieving contact at URL: {contact_url}")
    
    vcard_text = await client.get_contact(contact_url)
    if vcard_text is None:
        return None
    
    contact = parse_vcard_to_contact(vcard_text, contact_url, privacy)
    return contact
