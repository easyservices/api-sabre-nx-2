# Thin CardDAV adapter using direct HTTP (httpx), avoiding caldav’s missing CardDAV support.

import asyncio
import httpx
from fastapi import HTTPException
from typing import Optional, List
from urllib.parse import quote

from src.nextcloud.config import get_nextcloud_base_url
from src.nextcloud.libs.carddav_helpers import (
    contact_to_vcard,
    parse_vcard_to_contact,
    create_request_headers,
    create_request_xml,
    parse_xml_response,
)
from src.models.contact import Contact
from src import logger

_ASYNC_CLIENT: Optional[httpx.AsyncClient] = None


async def _client() -> httpx.AsyncClient:
    """Return a shared AsyncClient with pooling and sane timeouts."""
    global _ASYNC_CLIENT
    if _ASYNC_CLIENT is None:
        _ASYNC_CLIENT = httpx.AsyncClient(
            timeout=httpx.Timeout(10, connect=5, read=10, write=10),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )
    return _ASYNC_CLIENT


async def init_client():
    """Eagerly create the shared AsyncClient (for FastAPI startup hooks)."""
    await _client()


async def close_client():
    """Close the shared AsyncClient (for FastAPI shutdown hooks)."""
    global _ASYNC_CLIENT
    if _ASYNC_CLIENT is not None:
        await _ASYNC_CLIENT.aclose()
        _ASYNC_CLIENT = None


async def _request_with_retries(method: str, url: str, **kwargs) -> httpx.Response:
    """Issue an HTTP request with simple retry/backoff on 503/timeouts."""
    client = await _client()
    for attempt in range(3):
        try:
            resp = await client.request(method, url, **kwargs)
            logger.debug("carddav_request", extra={"method": method, "url": url, "status": resp.status_code, "attempt": attempt + 1})
            if resp.status_code in (503, 504) and attempt < 2:
                await asyncio.sleep(0.2 * (attempt + 1))
                continue
            return resp
        except (httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            logger.warning("carddav timeout", extra={"url": url, "attempt": attempt + 1, "error": str(exc)})
            if attempt == 2:
                raise
            await asyncio.sleep(0.2 * (attempt + 1))
    # Should not reach here
    raise HTTPException(status_code=503, detail="CardDAV request failed after retries")


def _addressbook_base(username: str, addressbook_name: Optional[str]) -> str:
    base_url = get_nextcloud_base_url().rstrip("/")
    book = addressbook_name or "contacts"
    encoded_username = quote(username or "", safe="")
    encoded_book = quote(book, safe="")
    return f"{base_url}/remote.php/dav/addressbooks/users/{encoded_username}/{encoded_book}"


async def list_contacts(credentials, addressbook_name: Optional[str], privacy: bool) -> List[Contact]:
    url = _addressbook_base(credentials.username, addressbook_name)
    headers = create_request_headers("")  # auth handled by httpx
    body = create_request_xml()
    resp = await _request_with_retries(
        "REPORT",
        url,
        headers=headers,
        content=body,
        auth=(credentials.username, credentials.password),
    )
    if resp.status_code not in (200, 207):
        raise HTTPException(status_code=resp.status_code, detail=f"CardDAV query failed: {resp.text}")
    contacts: List[Contact] = []
    for item in parse_xml_response(resp.text):
        try:
            parsed = parse_vcard_to_contact(item["vcard_data"], item.get("href"), privacy)
            if parsed:
                contacts.append(parsed)
        except Exception as exc:
            logger.error("Failed to parse vCard from %s: %s", item.get("href"), exc)
    return contacts


async def get_contact(credentials, uid: str, addressbook_name: Optional[str], privacy: bool) -> Optional[Contact]:
    if not uid:
        raise ValueError("Contact UID must be provided for retrieval")
    base = _addressbook_base(credentials.username, addressbook_name)
    url = f"{base.rstrip('/')}/{uid}.vcf"
    resp = await _request_with_retries("GET", url, auth=(credentials.username, credentials.password))
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=f"CardDAV GET failed: {resp.text}")
    return parse_vcard_to_contact(resp.content, url, privacy)


async def create_contact_client(credentials, contact: Contact, addressbook_name: Optional[str]) -> Contact:
    if not contact.uid:
        contact.uid = Contact.generate_uid()
    base = _addressbook_base(credentials.username, addressbook_name)
    url = f"{base.rstrip('/')}/{contact.uid}.vcf"
    vcard_data = contact_to_vcard(contact)
    headers = {
        "Content-Type": "text/vcard; charset=utf-8",
    }
    resp = await _request_with_retries(
        "PUT",
        url,
        content=vcard_data.encode("utf-8"),
        headers=headers,
        auth=(credentials.username, credentials.password),
    )
    if resp.status_code not in (200, 201, 204):
        raise HTTPException(status_code=resp.status_code, detail=f"CardDAV PUT failed: {resp.text}")
    contact.url = url
    return contact


async def update_contact_client(credentials, contact: Contact, addressbook_name: Optional[str]) -> Contact:
    if not contact.uid:
        raise HTTPException(status_code=400, detail="Contact UID is required for updates")
    base = _addressbook_base(credentials.username, addressbook_name)
    url = f"{base.rstrip('/')}/{contact.uid}.vcf"
    vcard_data = contact_to_vcard(contact)
    headers = {
        "Content-Type": "text/vcard; charset=utf-8",
    }
    resp = await _request_with_retries(
        "PUT",
        url,
        content=vcard_data.encode("utf-8"),
        headers=headers,
        auth=(credentials.username, credentials.password),
    )
    if resp.status_code not in (200, 201, 204):
        raise HTTPException(status_code=resp.status_code, detail=f"CardDAV PUT failed: {resp.text}")
    contact.url = url
    return contact


async def delete_contact_client(credentials, uid: str, addressbook_name: Optional[str]) -> bool:
    if not uid:
        raise ValueError("Contact UID must be provided for deletion")
    base = _addressbook_base(credentials.username, addressbook_name)
    url = f"{base.rstrip('/')}/{uid}.vcf"
    resp = await _request_with_retries("DELETE", url, auth=(credentials.username, credentials.password))
    if resp.status_code in (200, 204):
        return True
    if resp.status_code == 404:
        return False
    raise HTTPException(status_code=resp.status_code, detail=f"CardDAV DELETE failed: {resp.text}")
