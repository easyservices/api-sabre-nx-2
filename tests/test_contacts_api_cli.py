from __future__ import annotations

import json
from typing import Dict

import requests

from src.common.config import UsersSettings
from src.common.sec import gen_basic_auth_header
from src.models.contact import Contact
from src.nextcloud.config import get_api_proxy_url

settings = UsersSettings()
NEXTCLOUD_INTRANET_URL = get_api_proxy_url()


def _auth_headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": gen_basic_auth_header(
            settings.USERS["test4me"].NEXTCLOUD_USERNAME,
            settings.USERS["test4me"].NEXTCLOUD_PASSWORD,
        ),
    }


def _sample_contact_payload() -> Dict:
    return {
        "uid": Contact.generate_uid(),
        "full_name": "Jane Smith",
        "emails": [
            {"tag": "work", "email": "jane.smith@example.com"},
            {"tag": "home", "email": "jane.personal@example.com"},
        ],
        "phones": [{"tag": "cell", "number": "+1-555-987-6543"}],
        "addresses": [
            {
                "tag": "home",
                "street": "123 Main St",
                "city": "Anytown",
                "state": "CA",
                "postal_code": "12345",
                "country": "USA",
            }
        ],
        "birthday": "1985-04-15",
        "notes": "Created via API test",
        "groups": ["Test", "API"],
    }


def _create_contact_on_server() -> Dict:
    response = requests.post(
        f"{NEXTCLOUD_INTRANET_URL}/contacts",
        headers=_auth_headers(),
        json=_sample_contact_payload(),
    )
    response.raise_for_status()
    return response.json()


def _delete_contact(uid: str) -> None:
    response = requests.delete(
        f"{NEXTCLOUD_INTRANET_URL}/contacts/{uid}",
        headers=_auth_headers(),
    )
    if response.status_code not in (200, 204, 404):
        response.raise_for_status()


def test_get_all_contacts(is_debug: bool = False):
    response = requests.get(
        f"{NEXTCLOUD_INTRANET_URL}/contacts",
        headers=_auth_headers(),
    )
    if is_debug:
        print("### TEST GET ALL CONTACTS ###")
        print(f"Status Code: {response.status_code}")
    assert response.status_code == 200, (
        f"Expected 200 when listing contacts, got {response.status_code}: {response.text}"
    )

    contacts_response = response.json()
    if isinstance(contacts_response, dict):
        items = contacts_response.get("items")
        assert isinstance(items, list), "Expected 'items' list in contacts response payload"
    else:
        items = contacts_response
        assert isinstance(items, list), "Expected list response when fetching contacts"

    if is_debug:
        print(f"Found {len(items)} contacts")
        print(json.dumps(items, indent=4, sort_keys=True))


def test_search_contacts(is_debug: bool = False):
    search_criteria = {
        "full_name": "Einstein",
        "address": "Le Blennec",
        "group": "Perso",
        "search_type": "anyof",
    }

    response = requests.post(
        f"{NEXTCLOUD_INTRANET_URL}/contacts/search",
        headers=_auth_headers(),
        json=search_criteria,
    )

    if is_debug:
        print("\n### TEST SEARCH CONTACTS ###")
        print(f"Status Code: {response.status_code}")

    assert response.status_code == 200, (
        f"Expected 200 when searching contacts, got {response.status_code}: {response.text}"
    )

    contacts = response.json()
    if is_debug:
        print(f"Found {len(contacts)} matching contacts")
        print(json.dumps(contacts, indent=4, sort_keys=True))
    assert isinstance(contacts, list)


def test_create_contact(is_debug: bool = False):
    new_contact = _sample_contact_payload()
    response = requests.post(
        f"{NEXTCLOUD_INTRANET_URL}/contacts",
        headers=_auth_headers(),
        json=new_contact,
    )
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

    assert created_contact.get("uid") == new_contact["uid"]
    _delete_contact(created_contact["uid"])


def test_update_contact(is_debug: bool = False):
    created_contact = _create_contact_on_server()
    original_name = created_contact["full_name"]
    created_contact["full_name"] = f"{original_name} (Updated via API)"

    if "emails" not in created_contact or not created_contact["emails"]:
        created_contact["emails"] = [{"tag": "work", "email": "updated.api@example.com"}]
    else:
        created_contact["emails"][0]["email"] = "updated.api@example.com"

    if "notes" not in created_contact or not created_contact["notes"]:
        created_contact["notes"] = "Updated via API test"
    else:
        created_contact["notes"] += " - Updated via API test"

    response = requests.put(
        f"{NEXTCLOUD_INTRANET_URL}/contacts/{created_contact['uid']}",
        headers=_auth_headers(),
        json=created_contact,
    )
    if is_debug:
        print("\n### TEST UPDATE CONTACT ###")
        print(f"Status Code: {response.status_code}")

    assert response.status_code == 200, (
        f"Expected 200 when updating contact, got {response.status_code}: {response.text}"
    )

    result = response.json()
    assert result.get("full_name", "").endswith("(Updated via API)")
    _delete_contact(created_contact["uid"])


def test_delete_contact(is_debug: bool = False):
    created_contact = _create_contact_on_server()
    uid = created_contact["uid"]

    response = requests.delete(
        f"{NEXTCLOUD_INTRANET_URL}/contacts/{uid}",
        headers=_auth_headers(),
    )

    if is_debug:
        print("\n### TEST DELETE CONTACT ###")
        print(f"Status Code: {response.status_code}")

    assert response.status_code == 204, (
        f"Expected 204 when deleting contact, got {response.status_code}: {response.text}"
    )


def test_get_contact_by_uid(is_debug: bool = False):
    created_contact = _create_contact_on_server()
    uid = created_contact["uid"]

    response = requests.get(
        f"{NEXTCLOUD_INTRANET_URL}/contacts/{uid}",
        headers=_auth_headers(),
    )

    if is_debug:
        print("\n### TEST GET CONTACT BY UID ###")
        print(f"Status Code: {response.status_code}")

    assert response.status_code == 200, (
        f"Expected 200 when getting contact by UID, got {response.status_code}: {response.text}"
    )

    result = response.json()
    assert result.get("uid") == uid
    _delete_contact(uid)
