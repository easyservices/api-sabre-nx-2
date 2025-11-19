# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Manual API endpoint test script for the Nextcloud FastAPI app.

Results are printed to stdout for manual inspection.
"""

import sys
import json
import asyncio

from src.nextcloud import contacts
from src.common.config import UsersSettings # Import your config settings
from fastapi.security import HTTPBasicCredentials

settings = UsersSettings()

# --- Optional: Import Contact model for type checking ---
# This helps with code completion and clarity but isn't strictly required
# Adjust the path if your models are elsewhere
try:
    from src.models.contact import Contact, ContactSearchCriteria, Email, Phone, Address
except ImportError:
    Contact = None # Define as None if import fails, so isinstance check doesn't break
    ContactSearchCriteria = None
    Email = None
    Phone = None
    Address = None

""" TESTING API ENDPOINTS """

async def get_all_contacts(is_debug=False):
    """Test the get_all_contacts function to retrieve all contacts."""
    if is_debug:
        print ("### TEST get_all_contacts ###")
        print(f"Using user settings for: test4me")

    try:
        # Call the function using the user settings
        # Create HTTPBasicCredentials object
        credentials = HTTPBasicCredentials(
            username=settings.USERS["test4me"].NEXTCLOUD_USERNAME,
            password=settings.USERS["test4me"].NEXTCLOUD_PASSWORD
        )
        
        res = await contacts.get_all_contacts(
            credentials
        )

        # --- Nice Printing Logic ---
        if is_debug:
            print("\n--- Results ---")
            if isinstance(res, list):
                # Convert each object to a dictionary and dump the list as JSON
                print(json.dumps([contact.model_dump() for contact in res], indent=4))
            elif res is None:
                print("Received None")
            else:
                # If it's not a list, print its representation
                print(f"Received non-list result: {res!r}")
            print("-------------")
        
        if isinstance(res, list):
            return len(res)
        return 0

    except Exception as e:
        print(f"\n--- ERROR ---")
        print(f"An error occurred during the test: {e}")
        # If it's an HTTPException from your function, print details
        if hasattr(e, 'status_code') and hasattr(e, 'detail'):
            print(f"Status Code: {getattr(e, 'status_code', 'N/A')}")
            print(f"Detail: {getattr(e, 'detail', 'N/A')}")
        print("-------------")
        return None


async def search_contacts(is_debug=False):
    """Test the search_contacts function to search for contacts."""
    if is_debug:
        print("### TEST search_contacts ###")
        print(f"Using user settings for: test4me")

    try:
        # Create search criteria using the Pydantic model
        search_criteria = ContactSearchCriteria(
            full_name="Einstein",  # Search for contacts with "Einstein" in their name
            # email="example.com",  # Uncomment to add more search criteria
            # phone="555",
            address="Le Blennec",
            # birthday="1990-01-01",
            # notes="important",
            group="Perso",
            search_type="anyof"  # "anyof" (OR logic) or "allof" (AND logic)
        )

        if is_debug:
            print(f"Using search type: {search_criteria.search_type} ({'OR' if search_criteria.search_type == 'anyof' else 'AND'} logic)")

        # Call the search function
        # Create HTTPBasicCredentials object
        credentials = HTTPBasicCredentials(
            username=settings.USERS["test4me"].NEXTCLOUD_USERNAME,
            password=settings.USERS["test4me"].NEXTCLOUD_PASSWORD
        )
        
        res = await contacts.search_contacts(
            credentials,
            search_criteria
        )

        # --- Nice Printing Logic ---
        if is_debug:
            print("\n--- Search Results ---")
            print(f"Search criteria: {search_criteria}")
            if isinstance(res, list):
                print(f"Found {len(res)} matching contacts:")
                # Convert each object to a dictionary and dump the list as JSON
                print(json.dumps([contact.model_dump() for contact in res], indent=4))
            elif res is None:
                print("Received None")
            else:
                # If it's not a list, print its representation
                print(f"Received non-list result: {res!r}")
            print("-------------")
        
        if isinstance(res, list):
            return len(res)
        return 0

    except Exception as e:
        print(f"\n--- ERROR ---")
        print(f"An error occurred during the test: {e}")
        # If it's an HTTPException from your function, print details
        if hasattr(e, 'status_code') and hasattr(e, 'detail'):
            print(f"Status Code: {getattr(e, 'status_code', 'N/A')}")
            print(f"Detail: {getattr(e, 'detail', 'N/A')}")
        print("-------------")
        return None


async def create_contact_test(is_debug=False):
    """Test the create_contact function to create a new contact."""
    if is_debug:
        print("### TEST create_contact ###")
        print(f"Using user settings for: test4me")

    try:
        # Create a new Contact object
        new_contact = Contact(
            uid=Contact.generate_uid(),
            full_name="Test Contact",
            emails=[
                Email(tag="work", email="test.contact@example.com"),
                Email(tag="home", email="personal@example.com")
            ],
            phones=[
                Phone(tag="cell", number="+1-555-123-4567"),
                Phone(tag="work", number="+1-555-987-6543")
            ],
            addresses=[
                Address(
                    tag="home",
                    street="123 Main St",
                    city="Anytown",
                    state="CA",
                    postal_code="12345",
                    country="USA"
                )
            ],
            birthday="1990-01-01",
            notes="This is a test contact created via the Nextcloud CardDAV API",
            groups=["Test", "API", "Nextcloud"]
        )

        if is_debug:
            print(f"Creating contact: {new_contact.full_name}")

        # Call the create_contact function
        # Create HTTPBasicCredentials object
        credentials = HTTPBasicCredentials(
            username=settings.USERS["test4me"].NEXTCLOUD_USERNAME,
            password=settings.USERS["test4me"].NEXTCLOUD_PASSWORD
        )
        
        created_contact = await contacts.create_contact(
            credentials,
            new_contact
        )

        # --- Nice Printing Logic ---
        if is_debug:
            print("\n--- Create Contact Result ---")
            print(f"Contact created successfully with UID: {created_contact.uid}")
            print(f"vCard URL: {created_contact.url}")
            print(json.dumps(created_contact.model_dump(), indent=4))
            print("-------------")
        
        return created_contact

    except Exception as e:
        print(f"\n--- ERROR ---")
        print(f"An error occurred during the test: {e}")
        # If it's an HTTPException from your function, print details
        if hasattr(e, 'status_code') and hasattr(e, 'detail'):
            print(f"Status Code: {getattr(e, 'status_code', 'N/A')}")
            print(f"Detail: {getattr(e, 'detail', 'N/A')}")
        print("-------------")
        return None


async def update_contact_test(contact_to_update=None, is_debug=False):
    """Test the update_contact function to update a contact."""
    if is_debug:
        print("### TEST update_contact ###")
        print(f"Using user settings for: test4me")

    try:
        # If no contact is provided, get all contacts to find one to update
        # Create HTTPBasicCredentials object
        credentials = HTTPBasicCredentials(
            username=settings.USERS["test4me"].NEXTCLOUD_USERNAME,
            password=settings.USERS["test4me"].NEXTCLOUD_PASSWORD
        )
        
        if contact_to_update is None:
            all_contacts = await contacts.get_all_contacts(
                credentials
            )
            
            if not all_contacts:
                if is_debug:
                    print("No contacts found to update. Please create a contact first.")
                return None
            
            # Select the first contact to update
            contact_to_update = all_contacts[0]
        
        original_name = contact_to_update.full_name
        
        if is_debug:
            print(f"Selected contact to update: {contact_to_update.uid} - {original_name}")
        
        # Update the contact's information
        contact_to_update.full_name = f"{original_name} (Updated)"
        
        # Add a new email if there are none
        if not contact_to_update.emails:
            contact_to_update.emails = [Email(tag="work", email="updated.email@example.com")]
        else:
            # Or update the first email
            contact_to_update.emails[0].email = "updated.email@example.com"
        
        # Add a note about the update
        if not contact_to_update.notes:
            contact_to_update.notes = "Updated via API test"
        else:
            contact_to_update.notes += " - Updated via API test"
        
        if is_debug:
            print(f"Updating contact with new name: {contact_to_update.full_name}")
        
        # Call the update_contact function
        updated_contact = await contacts.update_contact(
            credentials,
            contact_to_update
        )
        
        # --- Nice Printing Logic ---
        if is_debug:
            print("\n--- Update Contact Result ---")
            print(f"Contact updated successfully with UID: {updated_contact.uid}")
            print(f"Original name: {original_name}")
            print(f"Updated name: {updated_contact.full_name}")
            print(f"vCard URL: {updated_contact.url}")
            print(json.dumps(updated_contact.model_dump(), indent=4))
            print("-------------")
        
        return updated_contact
        
    except Exception as e:
        print(f"\n--- ERROR ---")
        print(f"An error occurred during the test: {e}")
        # If it's an HTTPException from your function, print details
        if hasattr(e, 'status_code') and hasattr(e, 'detail'):
            print(f"Status Code: {getattr(e, 'status_code', 'N/A')}")
            print(f"Detail: {getattr(e, 'detail', 'N/A')}")
        print("-------------")
        return None


async def delete_contact_test(contact_to_delete=None, is_debug=False):
    """Test the delete_contact function to delete a contact."""
    if is_debug:
        print("### TEST delete_contact ###")
        print(f"Using user settings for: test4me")

    try:
        # If no contact is provided, get all contacts to find one to delete
        # Create HTTPBasicCredentials object
        credentials = HTTPBasicCredentials(
            username=settings.USERS["test4me"].NEXTCLOUD_USERNAME,
            password=settings.USERS["test4me"].NEXTCLOUD_PASSWORD
        )
        
        if contact_to_delete is None:
            all_contacts = await contacts.get_all_contacts(
                credentials
            )
            
            if not all_contacts:
                if is_debug:
                    print("No contacts found to delete. Please create a contact first.")
                return None
            
            # Select the first contact to delete
            contact_to_delete = all_contacts[0]
        
        uid = contact_to_delete.uid
        
        if is_debug:
            print(f"Selected contact to delete: {uid} - {contact_to_delete.full_name}")
        
        # Call the delete_contact function
        result = await contacts.delete_contact(
            credentials,
            uid
        )
        
        # --- Nice Printing Logic ---
        if is_debug:
            print("\n--- Delete Contact Result ---")
            print(f"Contact deleted successfully with UID: {uid}")
            print(json.dumps(result, indent=4))
            print("-------------")
        
        return result
        
    except Exception as e:
        print(f"\n--- ERROR ---")
        print(f"An error occurred during the test: {e}")
        # If it's an HTTPException from your function, print details
        if hasattr(e, 'status_code') and hasattr(e, 'detail'):
            print(f"Status Code: {getattr(e, 'status_code', 'N/A')}")
            print(f"Detail: {getattr(e, 'detail', 'N/A')}")
        print("-------------")
        return None


async def get_contact_by_uid_test(contact_to_retrieve=None, is_debug=False):
    """Test the get_contact_by_uid function to retrieve a single contact by UID."""
    if is_debug:
        print("### TEST get_contact_by_uid ###")
        print(f"Using user settings for: test4me")

    try:
        # If no contact is provided, get all contacts to find one to retrieve
        # Create HTTPBasicCredentials object
        credentials = HTTPBasicCredentials(
            username=settings.USERS["test4me"].NEXTCLOUD_USERNAME,
            password=settings.USERS["test4me"].NEXTCLOUD_PASSWORD
        )
        
        if contact_to_retrieve is None:
            all_contacts = await contacts.get_all_contacts(
                credentials
            )
            
            if not all_contacts:
                if is_debug:
                    print("No contacts found to retrieve. Please create a contact first.")
                return None
            
            # Select the first contact to retrieve
            contact_to_retrieve = all_contacts[0]
        
        uid = contact_to_retrieve.uid
        
        if is_debug:
            print(f"Selected contact to retrieve: {uid} - {contact_to_retrieve.full_name}")
        
        # Call the get_contact_by_uid function
        retrieved_contact = await contacts.get_contact_by_uid(
            credentials,
            uid
        )
        
        # --- Nice Printing Logic ---
        if is_debug:
            print("\n--- Get Contact By UID Result ---")
            if retrieved_contact:
                print(f"Contact retrieved successfully with UID: {retrieved_contact.uid}")
                print(f"Full name: {retrieved_contact.full_name}")
                print(f"vCard URL: {retrieved_contact.url}")
                print(json.dumps(retrieved_contact.model_dump(), indent=4))
            else:
                print(f"No contact found with UID: {uid}")
            print("-------------")
        
        return retrieved_contact
        
    except Exception as e:
        print(f"\n--- ERROR ---")
        print(f"An error occurred during the test: {e}")
        # If it's an HTTPException from your function, print details
        if hasattr(e, 'status_code') and hasattr(e, 'detail'):
            print(f"Status Code: {getattr(e, 'status_code', 'N/A')}")
            print(f"Detail: {getattr(e, 'detail', 'N/A')}")
        print("-------------")
        return None


if __name__ == "__main__":
    # Run all tests sequentially and check for success/failure
    
    # Test get_all_contacts
    num_all = asyncio.run(get_all_contacts())
    if num_all is None:
        print(f"FAILURE: get_all_contacts returned None")
        sys.exit(1)
    print(f"SUCCESS: get_all_contacts returned {num_all} record(s)")
    
    # Test search_contacts
    num = asyncio.run(search_contacts())
    if num is None:
        print(f"FAILURE: search_contacts returned None")
        sys.exit(1)
    print(f"SUCCESS: search_contacts returned {num} record(s)")
    
    # Test create_contact
    created_contact = asyncio.run(create_contact_test())
    if created_contact is None:
        print(f"FAILURE: create_contact_test did not return a created contact")
        sys.exit(1)
    print(f"SUCCESS: create_contact_test returned contact with full_name: {created_contact.full_name}")
    
    # Test get_contact_by_uid using the created contact
    retrieved_contact = asyncio.run(get_contact_by_uid_test(created_contact))
    if retrieved_contact is None:
        print(f"FAILURE: get_contact_by_uid_test did not return a contact")
        sys.exit(1)
    print(f"SUCCESS: get_contact_by_uid_test returned contact with full_name: {retrieved_contact.full_name}")
    
    # Test update_contact using the created contact
    updated_contact = asyncio.run(update_contact_test(created_contact))
    if updated_contact is None:
        print(f"FAILURE: update_contact_test did not return an updated contact")
        sys.exit(1)
    print(f"SUCCESS: update_contact_test returned updated contact with full_name: {updated_contact.full_name}")
    
    # Test delete_contact using the updated contact
    deleted_result = asyncio.run(delete_contact_test(updated_contact))
    if deleted_result is None:
        print(f"FAILURE: delete_contact_test did not return a result")
        sys.exit(1)
    print(f"SUCCESS: delete_contact_test returned: {deleted_result.get('message')}")
