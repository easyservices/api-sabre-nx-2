# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""
Manual API endpoint test script for the Nextcloud FastAPI app.

Results are printed to stdout for manual inspection.
"""

import json
import sys

from src.models.contact import Contact
from .support.contacts_client import ContactsApiClient

contacts_client = ContactsApiClient()

""" TESTING API ENDPOINTS """

def run_get_all_contacts(is_debug=False):
    """Test the GET /contacts endpoint to retrieve all contacts."""
    response = contacts_client.list_contacts()
    if is_debug:
        print("### TEST GET ALL CONTACTS ###")
        print(f"Status Code: {response.status_code}")
    assert response.status_code == 200, (
        f"Expected 200 when listing contacts, got {response.status_code}: {response.text}"
    )

    contacts = response.json()
    if is_debug:
        print(f"Found {len(contacts)} contacts")
        print(json.dumps(contacts, indent=4, sort_keys=True))
    return len(contacts)  # Return the number of contacts found


def test_get_all_contacts(is_debug=False):
    run_get_all_contacts(is_debug=is_debug)


def run_search_contacts(is_debug=False):
    """Test the POST /contacts/search endpoint to search for contacts."""
    # Example search criteria - modify as needed
    search_criteria = {
        "full_name": "Einstein",  # Search for contacts with "Einstein" in their name
        # You can add more search criteria as needed:
        # "email": "example.com",
        # "phone": "555",
        "address": "Le Blennec",
        # "birthday": "1990-01-01",
        # "notes": "important",
        "group": "Perso",
        "search_type": "anyof"  # "anyof" (OR logic) or "allof" (AND logic)
    }
    
    response = contacts_client.search_contacts(search_criteria)
    
    if is_debug:
        print("\n### TEST SEARCH CONTACTS ###")
        print(f"Search criteria: {search_criteria}")
        print(f"Status Code: {response.status_code}")
    
    assert response.status_code == 200, (
        f"Expected 200 when searching contacts, got {response.status_code}: {response.text}"
    )

    contacts = response.json()
    if is_debug:
        print(f"Found {len(contacts)} matching contacts")
        print(json.dumps(contacts, indent=4, sort_keys=True))
    return len(contacts)  # Return the number of contacts found


def test_search_contacts(is_debug=False):
    run_search_contacts(is_debug=is_debug)


def run_create_contact(is_debug=False):
    """Test the POST /contacts endpoint to create a new contact."""
    # Example contact data
    new_contact = {
        "uid": Contact.generate_uid(),  # Generate a UUID using the Contact class method
        "full_name": "Jane Smith",
        "emails": [
            {
                "tag": "work",
                "email": "jane.smith@example.com"
            },
            {
                "tag": "home",
                "email": "jane.personal@example.com"
            }
        ],
        "phones": [
            {
                "tag": "cell",
                "number": "+1-555-987-6543"
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
        "birthday": "1985-04-15",
        "notes": "Created via API test",
        "groups": ["Test", "API"]
    }
    
    response = contacts_client.create_contact(new_contact)
    if is_debug:
        print("\n### TEST CREATE CONTACT ###")
        print(f"Status Code: {response.status_code}")
    
    assert response.status_code in (200, 201), (
        f"Expected 200/201 when creating contact, got {response.status_code}: {response.text}"
    )

    created_contact = response.json()
    if is_debug:
        print("Contact created successfully:")
        print(json.dumps(created_contact, indent=4, sort_keys=True))
    
    return created_contact


def test_create_contact(is_debug=False):
    run_create_contact(is_debug=is_debug)


def run_update_contact(contact=None, is_debug=False):
    """Test the PUT /contacts/{uid} endpoint to update a contact."""
    if contact is None:
        if is_debug:
            print("\n### TEST UPDATE CONTACT ###")
            print("No contacts found to update. Please create a contact first.")
        return
      
    # Update the contact's information
    original_name = contact["full_name"]
    contact["full_name"] = f"{original_name} (Updated via API)"
    
    # Update or add an email
    if "emails" not in contact or not contact["emails"]:
        contact["emails"] = [{"tag": "work", "email": "updated.api@example.com"}]
    else:
        contact["emails"][0]["email"] = "updated.api@example.com"
    
    # Update or add notes
    if "notes" not in contact or not contact["notes"]:
        contact["notes"] = "Updated via API test"
    else:
        contact["notes"] += " - Updated via API test"
    
    # Send the update request
    uid = contact.get("uid")
    response = contacts_client.update_contact(uid, contact)
    if is_debug:
        print("\n### TEST UPDATE CONTACT ###")
        print(f"Status Code: {response.status_code}")
    
    assert response.status_code == 200, (
        f"Expected 200 when updating contact, got {response.status_code}: {response.text}"
    )

    result = response.json()
    if is_debug:
        print("Contact updated successfully:")
        print(f"Original name: {original_name}")
        print(f"Updated name: {result.get('full_name')}")
        print(json.dumps(result, indent=4, sort_keys=True))
    return result


def test_update_contact(contact=None, is_debug=False):
    run_update_contact(contact=contact, is_debug=is_debug)


def run_delete_contact(contact=None, is_debug=False):
    """Test the DELETE /contacts/{uid} endpoint to delete a contact."""
    if contact is None:
        if is_debug:
            print("\n### TEST DELETE CONTACT ###")
            print("No contact provided to delete. Please create a contact first.")
        return None
    
    # Get the UID from the contact
    uid = contact.get("uid")
    if not uid:
        if is_debug:
            print("\n### TEST DELETE CONTACT ###")
            print("Contact does not have a UID. Cannot delete.")
        return None
    
    # Send the delete request
    response = contacts_client.delete_contact(uid)
    
    if is_debug:
        print("\n### TEST DELETE CONTACT ###")
        print(f"Status Code: {response.status_code}")
    
    assert response.status_code == 204, (
        f"Expected 204 when deleting contact, got {response.status_code}: {response.text}"
    )

    if is_debug:
        print(f"Contact deleted successfully: {contact}")
    return contact


def test_delete_contact(contact=None, is_debug=False):
    run_delete_contact(contact=contact, is_debug=is_debug)


def run_get_contact_by_uid(contact=None, is_debug=False):
    """Test the GET /contacts/{uid} endpoint to retrieve a single contact by UID."""
    if contact is None:
        if is_debug:
            print("\n### TEST GET CONTACT BY UID ###")
            print("No contact provided to retrieve. Please create a contact first.")
        return None
    
    # Get the UID from the contact
    uid = contact.get("uid")
    if not uid:
        if is_debug:
            print("\n### TEST GET CONTACT BY UID ###")
            print("Contact does not have a UID. Cannot retrieve.")
        return None
    
    # Send the get request
    response = contacts_client.get_contact(uid)
    
    if is_debug:
        print("\n### TEST GET CONTACT BY UID ###")
        print(f"Status Code: {response.status_code}")
    
    assert response.status_code == 200, (
        f"Expected 200 when getting contact by UID, got {response.status_code}: {response.text}"
    )

    result = response.json()
    if is_debug:
        print("Contact retrieved successfully:")
        print(json.dumps(result, indent=4, sort_keys=True))
    return result


def test_get_contact_by_uid(contact=None, is_debug=False):
    run_get_contact_by_uid(contact=contact, is_debug=is_debug)


# Run the tests
if __name__ == "__main__":
    num_all = run_get_all_contacts()
    if num_all is None:
        print("FAILURE: get_all_contacts test returned None")
        sys.exit(1)
    print(f"SUCCESS: get_all_contacts test returned {num_all} record(s)")

    num = run_search_contacts()
    if num is None:
        print("FAILURE: search_contacts test returned None")
        sys.exit(1)
    print(f"SUCCESS: search_contacts test returned {num} record(s)")

    created_contact = run_create_contact()
    if created_contact is None:
        print("FAILURE: create_contact test did not return a created contact")
        sys.exit(1)
    print(f"SUCCESS: create_contact test returned contact with full_name: {created_contact.get('full_name')}")

    retrieved_contact = run_get_contact_by_uid(created_contact)
    if retrieved_contact is None:
        print("FAILURE: get_contact_by_uid test did not return a contact")
        sys.exit(1)
    print(f"SUCCESS: get_contact_by_uid test returned contact with full_name: {retrieved_contact.get('full_name')}")

    updated_contact = run_update_contact(created_contact)
    if updated_contact is None:
        print("FAILURE: update_contact test did not return an updated contact")
        sys.exit(1)
    print(f"SUCCESS: update_contact test returned updated contact with full_name: {updated_contact.get('full_name')}")

    deleted_result = run_delete_contact(updated_contact)
    if deleted_result is None:
        print("FAILURE: delete_contact test did not return a result")
        sys.exit(1)
    print(f"SUCCESS: delete_contact test returned deleted contact with full_name: {deleted_result.get('full_name')}")

