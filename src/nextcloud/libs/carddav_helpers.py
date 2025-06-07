# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Helper functions for CardDAV operations.

This module provides utility functions for working with CardDAV,
including request creation, response parsing, and vCard processing.
"""

from fastapi import HTTPException
from src.models.contact import Address, Contact, Email, Phone
from typing import List, Dict, Any, Optional
import vobject
import xml.etree.ElementTree as ET

from src.nextcloud import (
    API_ERR_ADDRESSBOOK_NOT_FOUND,
    API_ERR_AUTH_FAILED,
    API_ERR_AUTH_REFUSED,
    API_ERR_SERVER_ERROR,
    API_ERR_SERVER_UNATTENDED_RESPONSE
)
from src.nextcloud.libs import PRIVACY_MODE_TXT
from src import logger


def create_request_headers(auth_header: str) -> Dict[str, str]:
    """
    Create headers for the CardDAV request.
    
    Args:
        auth_header (str): HTTP Authorization header value.
        
    Returns:
        Dict[str, str]: Headers dictionary for the request.
    """
    return {
        "Depth": "1",
        "Content-Type": "application/xml; charset=utf-8",
        "authorization": auth_header
    }


def create_request_xml() -> str:
    """
    Create the XML data for the CardDAV request.
    
    Returns:
        str: XML data for the request.
    """
    return """<?xml version="1.0"?>
                <card:addressbook-query xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
                <d:prop>
                    <d:getetag/>
                    <card:address-data/>
                </d:prop>
                </card:addressbook-query>"""


def handle_response_status(status_code: int, response_text: str) -> None:
    """
    Handle HTTP status codes and raise appropriate exceptions.
    
    Args:
        status_code (int): HTTP status code.
        response_text (str): Response text from the server.
        
    Raises:
        HTTPException: For authentication, authorization, server, or parsing errors.
    """
    if status_code == 401:
        raise HTTPException(status_code=401, detail=API_ERR_AUTH_FAILED)
    if status_code == 403:
        raise HTTPException(status_code=403, detail=API_ERR_AUTH_REFUSED)
    if status_code == 404:
        raise HTTPException(status_code=404, detail=API_ERR_ADDRESSBOOK_NOT_FOUND)
    if status_code >= 500:
        raise HTTPException(status_code=500, detail=API_ERR_SERVER_ERROR)
    if status_code != 207:
        raise HTTPException(status_code=status_code, detail=f"{API_ERR_SERVER_UNATTENDED_RESPONSE}: {response_text}")


def parse_xml_response(response_text: str) -> List[Dict[str, Any]]:
    """
    Parse the XML response from the CardDAV server.
    
    Args:
        response_text (str): XML response text from the server.
        
    Returns:
        List[Dict[str, Any]]: List of dictionaries containing href and vcard_data.
    """
    result = []
    root = ET.fromstring(response_text)
    
    for response_element in root.findall('.//{DAV:}response'):
        href_element = response_element.find('.//{DAV:}href')
        vcard_data_element = response_element.find('.//{urn:ietf:params:xml:ns:carddav}address-data')
        
        if vcard_data_element is not None and vcard_data_element.text:
            result.append({
                'href': href_element.text if href_element is not None else None,
                'vcard_data': vcard_data_element.text
            })
    
    return result


def parse_vcard_to_contact(vcard_data: str, href: Optional[str] = None, privacy: Optional[bool] = False) -> Optional[Contact]:
    """
    Parse a vCard string into a Contact object.
    
    This function extracts relevant information from a vCard string and creates a Contact object.
    It handles various vCard properties including:
    - UID
    - Full name (FN)
    - Email addresses
    - Phone numbers
    - Physical addresses
    - Birthday (formatted as YYYY-MM-DD)
    - Notes
    - Groups/categories
    
    Args:
        vcard_data (str): vCard data as string.
        href (Optional[str]): The href/URI of the vCard.
        
    Returns:
        Optional[Contact]: Contact object or None if parsing fails.
    """
    try:
        vcard = vobject.readOne(vcard_data)
        
        # Extract UID for debugging purposes
        uid = str(vcard.uid.value) if hasattr(vcard, 'uid') else ""
        
        # Extract name information
        full_name = str(vcard.fn.value) if hasattr(vcard, 'fn') else ""
        
        # Extract email addresses
        emails = []
        if hasattr(vcard, 'email_list'):
            for e in vcard.email_list:
                if hasattr(e, 'value'):
                    try:
                        # Safely extract type_param
                        tag = str(e.type_param) if hasattr(e, 'type_param') and e.type_param is not None else ""
                        emails.append(Email(email=str(e.value), tag=tag))
                    except Exception as email_error:
                        logger.error(f"Error parsing email for contact UID {uid}: {email_error}")
                        logger.error(f"Email object: {e}")
                        # Add email without tag as fallback
                        emails.append(Email(email=str(e.value), tag=""))
        
        # Extract phone numbers
        phones = []
        if hasattr(vcard, 'tel_list'):
            for p in vcard.tel_list:
                if hasattr(p, 'value'):
                    try:
                        # Safely extract type_param
                        tag = str(p.type_param) if hasattr(p, 'type_param') and p.type_param is not None else ""
                        phones.append(Phone(number=str(p.value), tag=tag))
                    except Exception as phone_error:
                        logger.error(f"Error parsing phone for contact UID {uid}: {phone_error}")
                        logger.error(f"Phone object: {p}")
                        # Add phone without tag as fallback
                        phones.append(Phone(number=str(p.value), tag=""))
        
        # Extract addresses
        addresses = []
        if hasattr(vcard, 'adr_list'):
            for adr in vcard.adr_list:
                if hasattr(adr, 'value'):
                    try:
                        # Safely extract type_param
                        tag = str(adr.type_param) if hasattr(adr, 'type_param') and adr.type_param is not None else ""

                        # If privacy is enabled
                        street=str(adr.value.street) if hasattr(adr.value, 'street') else None
                        city=str(adr.value.city) if hasattr(adr.value, 'city') else None
                        postal_code=str(adr.value.code) if hasattr(adr.value, 'code') else None
                        if privacy is True:
                            city = PRIVACY_MODE_TXT
                            street = PRIVACY_MODE_TXT
                            postal_code = None

                        addresses.append(Address(
                            street=street,
                            city=city,
                            state=str(adr.value.region) if hasattr(adr.value, 'region') else None,
                            postal_code=postal_code,
                            country=str(adr.value.country) if hasattr(adr.value, 'country') else None,
                            tag=tag
                        ))
                    except Exception as address_error:
                        logger.error(f"Error parsing address for contact UID {uid}: {address_error}")
                        logger.error(f"Address object: {adr}")
                        # Add address without tag as fallback
                        
                        # If privacy is enabled
                        street=str(adr.value.street) if hasattr(adr.value, 'street') else None
                        city=str(adr.value.city) if hasattr(adr.value, 'city') else None
                        postal_code=str(adr.value.code) if hasattr(adr.value, 'code') else None
                        if privacy is True:
                            city = PRIVACY_MODE_TXT
                            street = PRIVACY_MODE_TXT
                            postal_code = None

                        addresses.append(Address(
                            street=street,
                            city=city,
                            state=str(adr.value.region) if hasattr(adr.value, 'region') else None,
                            postal_code=postal_code,
                            country=str(adr.value.country) if hasattr(adr.value, 'country') else None,
                            tag=""
                        ))
        
        # Extract birthday and format as YYYY-MM-DD
        birthday = None
        if hasattr(vcard, 'bday'):
            try:
                # Get the raw birthday value
                bday_value = str(vcard.bday.value)

                if privacy is True:
                    # If privacy is enabled, return None for birthday
                    birthday = None
                    return
                
                # Handle different vCard birthday formats
                # Format 1: YYYYMMDD
                if len(bday_value) == 8 and bday_value.isdigit():
                    birthday = f"{bday_value[0:4]}-{bday_value[4:6]}-{bday_value[6:8]}"
                # Format 2: YYYY-MM-DD already
                elif len(bday_value) == 10 and bday_value[4] == '-' and bday_value[7] == '-':
                    birthday = bday_value
                # Format 3: YYYYMMDDTHHMMSSZ (ISO format with time)
                elif len(bday_value) > 8 and 'T' in bday_value:
                    date_part = bday_value.split('T')[0]
                    if len(date_part) == 8:
                        birthday = f"{date_part[0:4]}-{date_part[4:6]}-{date_part[6:8]}"
                    else:
                        birthday = date_part  # Already formatted or unknown format
                else:
                    # Unknown format, store as is
                    birthday = bday_value
            except Exception as e:
                logger.error(f"Error parsing birthday: {e}")
        
        # Extract notes
        notes = None
        if hasattr(vcard, 'note'):
            # If privacy is enabled, return None for notes
            if privacy is False:
                notes = str(vcard.note.value)
            else:
                notes = PRIVACY_MODE_TXT
        
        # Extract contact groups/categories
        groups = []
        
        # Method 1: Extract from CATEGORIES property
        if hasattr(vcard, 'categories'):
            if hasattr(vcard.categories, 'value'):
                if isinstance(vcard.categories.value, list):
                    groups.extend([str(cat) for cat in vcard.categories.value])
                else:
                    # Sometimes it's a single string
                    groups.append(str(vcard.categories.value))
        
        # Method 2: Extract from X-ADDRESSBOOKSERVER-GROUP property (used by some CardDAV servers)
        for child in vcard.getChildren():
            if child.name.upper() == 'X-ADDRESSBOOKSERVER-GROUP':
                if hasattr(child, 'value') and child.value:
                    groups.append(str(child.value))
        
        # Method 3: Extract from X-ADDRESSBOOKSERVER-MEMBER property (used by some CardDAV servers)
        for child in vcard.getChildren():
            if child.name.upper() == 'X-ADDRESSBOOKSERVER-MEMBER':
                if hasattr(child, 'value') and child.value:
                    # Extract group name from urn:uuid:group-name format
                    value = str(child.value)
                    if 'urn:uuid:' in value:
                        group_name = value.split('urn:uuid:')[-1]
                        groups.append(group_name)
                    else:
                        groups.append(value)
        
        # Create and return Contact object
        return Contact(
            uid=uid,
            full_name=full_name,
            emails=emails,
            phones=phones,
            addresses=addresses,
            vcs_uri=href,
            birthday=birthday,
            notes=notes,
            groups=groups
        )
    
    except Exception as e:
        logger.error(f"Error parsing vCard: {e}")
        logger.error(f"Contact UID: {uid if 'uid' in locals() else 'Unknown'}")
        logger.error(f"Contact full_name: {full_name if 'full_name' in locals() else 'Unknown'}")
        logger.error(f"vCard href: {href}")
        logger.error(f"vCard data (first 500 chars): {vcard_data[:500] if vcard_data else 'None'}")
        return None


def create_prop_filter(property_name: str, search_value: str, match_type: str = "contains") -> str:
    """
    Create a CardDAV property filter XML string for a specific property.
    
    Args:
        property_name (str): The vCard property name to filter on (e.g., "FN", "EMAIL").
        search_value (str): The value to search for.
        match_type (str): The match type, either "contains", "equals", "starts-with", or "ends-with".
        
    Returns:
        str: XML string for the property filter.
    """
    return f"""
        <card:prop-filter name="{property_name}">
            <card:text-match collation="i;unicode-casemap" match-type="{match_type}">{search_value}</card:text-match>
        </card:prop-filter>
    """


def create_search_filter_xml(search_criteria: Dict[str, str], search_type: str = "anyof") -> str:
    """
    Create a CardDAV filter XML string based on search criteria.
    
    Args:
        search_criteria (Dict[str, str]): Dictionary mapping property names to search values.
        search_type (str): The search type, either "anyof" (OR logic) or "allof" (AND logic).
        
    Returns:
        str: XML string for the filter, or empty string if no criteria provided.
    """
    # Property name mapping from API fields to vCard properties
    property_mapping = {
        "uid": "UID",
        "full_name": "FN",
        "email": "EMAIL",
        "phone": "TEL",
        "address": "ADR",
        "birthday": "BDAY",
        "group": "CATEGORIES"
    }
    
    prop_filters = []
    
    for field, value in search_criteria.items():
        if field in property_mapping and value and len(str(value)) > 0:
            prop_filters.append(create_prop_filter(property_mapping[field], str(value)))
    
    if not prop_filters:
        return ""
    
    return f"""
        <card:filter test="{search_type}">
            {''.join(prop_filters)}
        </card:filter>
    """


def create_search_request_xml(search_criteria: Dict[str, str] = None, search_type: str = "anyof") -> str:
    """
    Create the complete XML data for a CardDAV search request.
    
    Args:
        search_criteria (Dict[str, str], optional): Dictionary of search criteria.
        search_type (str, optional): The search type, either "anyof" (OR logic) or "allof" (AND logic).
        
    Returns:
        str: Complete XML data for the request.
    """
    filter_xml = ""
    if search_criteria:
        filter_xml = create_search_filter_xml(search_criteria, search_type)
    
    return f"""<?xml version="1.0"?>
        <card:addressbook-query xmlns:d="DAV:" xmlns:card="urn:ietf:params:xml:ns:carddav">
            <d:prop>
                <d:getetag/>
                <card:address-data/>
            </d:prop>
            {filter_xml}
        </card:addressbook-query>"""


def contact_to_vcard(contact: Contact) -> str:
    """
    Convert a Contact object to a vCard string.
    
    This function creates a vCard representation of a Contact object using the vobject library.
    It handles all the fields in the Contact model, including:
    - UID
    - Full name
    - Email addresses
    - Phone numbers
    - Physical addresses
    - Birthday
    - Notes
    - Groups/categories
    
    Args:
        contact (Contact): The Contact object to convert.
        
    Returns:
        str: vCard string representation of the Contact.
    """
    # Create a new vCard
    vcard = vobject.vCard()
    
    # Add UID
    uid = vcard.add('uid')
    uid.value = contact.uid
    
    # Add full name
    fn = vcard.add('fn')
    fn.value = contact.full_name
    
    # Add email addresses
    if contact.emails:
        for email in contact.emails:
            email_prop = vcard.add('email')
            email_prop.value = email.email
            if email.tag:
                email_prop.type_param = email.tag
    
    # Add phone numbers
    if contact.phones:
        for phone in contact.phones:
            tel = vcard.add('tel')
            tel.value = phone.number
            if phone.tag:
                tel.type_param = phone.tag
    
    # Add addresses
    if contact.addresses:
        for address in contact.addresses:
            adr = vcard.add('adr')
            adr.value = vobject.vcard.Address(
                street=address.street or '',
                city=address.city or '',
                region=address.state or '',
                code=address.postal_code or '',
                country=address.country or ''
            )
            if address.tag:
                adr.type_param = address.tag
    
    # Add birthday
    if contact.birthday:
        bday = vcard.add('bday')
        bday.value = contact.birthday
    
    # Add notes
    if contact.notes:
        note = vcard.add('note')
        note.value = contact.notes
    
    # Add groups/categories
    if contact.groups and len(contact.groups) > 0:
        categories = vcard.add('categories')
        categories.value = contact.groups
    
    # Return the serialized vCard
    return vcard.serialize()


def create_vcard_headers(auth_header: str) -> Dict[str, str]:
    """
    Create headers for the CardDAV PUT request to create or update a vCard.
    
    Args:
        auth_header (str): HTTP Authorization header value.
        
    Returns:
        Dict[str, str]: Headers dictionary for the request.
    """
    return {
        "Content-Type": "text/vcard; charset=utf-8",
        "authorization": auth_header
    }