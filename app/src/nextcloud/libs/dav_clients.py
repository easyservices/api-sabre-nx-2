"""Utility clients for CardDAV and CalDAV network interactions."""

import asyncio
import atexit
import os
from typing import Dict, Optional, Tuple

import aiohttp
from fastapi import HTTPException

from src.nextcloud import API_ERR_CONNECTION_ERROR
from src.nextcloud.libs.carddav_helpers import (
    create_request_headers,
    create_request_xml,
    create_search_request_xml,
    create_vcard_headers,
    handle_response_status,
)
from src.nextcloud.libs.caldav_helpers import (
    create_caldav_event_headers,
    create_caldav_request_headers,
    create_calendar_query_xml,
    handle_caldav_response_status,
)


_DAV_TOTAL_TIMEOUT = float(os.getenv("NEXTCLOUD_DAV_TIMEOUT", "30"))
_DAV_CONNECT_TIMEOUT = float(os.getenv("NEXTCLOUD_DAV_CONNECT_TIMEOUT", "10"))
_DAV_MAX_CONNECTIONS = int(os.getenv("NEXTCLOUD_DAV_MAX_CONNECTIONS", "50"))
_DAV_MAX_RETRIES = int(os.getenv("NEXTCLOUD_DAV_MAX_RETRIES", "2"))
_DAV_BACKOFF = float(os.getenv("NEXTCLOUD_DAV_BACKOFF", "0.4"))
_DAV_PROXY = os.getenv("NEXTCLOUD_DAV_PROXY")
_DAV_TRUST_ENV = os.getenv("NEXTCLOUD_DAV_TRUST_ENV", "1").lower() not in {"0", "false", "no"}

_shared_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()


async def _get_shared_session() -> aiohttp.ClientSession:
    """Create (or reuse) a shared aiohttp session with pooling and TLS config."""
    global _shared_session
    if _shared_session and not _shared_session.closed:
        return _shared_session

    async with _session_lock:
        if _shared_session and not _shared_session.closed:
            return _shared_session

        timeout = aiohttp.ClientTimeout(total=_DAV_TOTAL_TIMEOUT, connect=_DAV_CONNECT_TIMEOUT)
        connector = aiohttp.TCPConnector(limit=_DAV_MAX_CONNECTIONS, ttl_dns_cache=300)
        _shared_session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            trust_env=_DAV_TRUST_ENV,
        )
        return _shared_session


def _close_shared_session() -> None:
    """Ensure the shared session is closed when the process exits."""
    session = globals().get("_shared_session")
    if session and not session.closed:
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(session.close())
        finally:
            loop.close()


atexit.register(_close_shared_session)


class BaseDavClient:
    """Shared functionality for DAV clients."""

    def __init__(self, base_url: str, auth_header: str, proxy_url: Optional[str] = None) -> None:
        self.base_url = base_url if base_url.endswith('/') else f"{base_url}/"
        self.auth_header = auth_header
        self.proxy = proxy_url if proxy_url is not None else _DAV_PROXY

    def build_url(self, relative_path: str) -> str:
        """Join the base URL with a relative resource path."""
        relative = relative_path.lstrip('/')
        return f"{self.base_url}{relative}"

    async def _request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str],
        data: Optional[str] = None
    ) -> Tuple[int, str, aiohttp.typedefs.LooseHeaders]:
        """Execute an HTTP request and return the (status, text, headers) tuple with retries."""
        attempt = 0
        last_exc: Optional[aiohttp.ClientError] = None

        while attempt <= _DAV_MAX_RETRIES:
            attempt += 1
            try:
                session = await _get_shared_session()
                async with session.request(
                    method,
                    url,
                    headers=headers,
                    data=data,
                    proxy=self.proxy,
                ) as response:
                    text = await response.text()
                    return response.status, text, response.headers
            except aiohttp.ClientError as exc:
                last_exc = exc
                if attempt > _DAV_MAX_RETRIES:
                    break
                await asyncio.sleep(_DAV_BACKOFF * attempt)

        raise HTTPException(
            status_code=500,
            detail=f"{API_ERR_CONNECTION_ERROR}: {last_exc}",
        ) from last_exc


class CardDavClient(BaseDavClient):
    """Async helper for CardDAV operations."""

    async def report_addressbook(self) -> str:
        """Fetch all contacts via REPORT."""
        headers = create_request_headers(self.auth_header)
        xml_data = create_request_xml()
        status, text, _ = await self._request("REPORT", self.base_url, headers, data=xml_data)
        handle_response_status(status, text)
        return text

    async def search_addressbook(self, criteria: Dict[str, str], search_type: str) -> str:
        """Execute a REPORT with filters."""
        headers = create_request_headers(self.auth_header)
        xml_data = create_search_request_xml(criteria, search_type)
        status, text, _ = await self._request("REPORT", self.base_url, headers, data=xml_data)
        handle_response_status(status, text)
        return text

    async def get_contact(self, contact_url: str) -> Tuple[Optional[str], Optional[str]]:
        """Retrieve a single vCard."""
        headers = {"authorization": self.auth_header}
        status, text, response_headers = await self._request("GET", contact_url, headers)
        if status == 404:
            return None, None
        if status != 200:
            handle_response_status(status, text)
        return text, response_headers.get("ETag")

    async def create_contact(self, contact_url: str, vcard_data: str) -> Optional[str]:
        """Create a contact via PUT."""
        headers = create_vcard_headers(self.auth_header)
        status, text, response_headers = await self._request("PUT", contact_url, headers, data=vcard_data)
        if status not in (201, 204):
            if status == 405:
                raise HTTPException(
                    status_code=405,
                    detail=f"Cannot create contact at this URL. The server responded: {text}"
                )
            handle_response_status(status, text)
        return response_headers.get("ETag")

    async def update_contact(self, contact_url: str, vcard_data: str, etag: Optional[str] = None) -> Optional[str]:
        """Update an existing contact."""
        headers = create_vcard_headers(self.auth_header)
        if etag:
            headers["If-Match"] = etag
        status, text, response_headers = await self._request("PUT", contact_url, headers, data=vcard_data)
        if status not in (200, 201, 204):
            if status == 404:
                raise HTTPException(
                    status_code=404,
                    detail=f"Contact not found at {contact_url}. The server responded: {text}"
                )
            if status == 405:
                raise HTTPException(
                    status_code=405,
                    detail=f"Cannot update contact at this URL. The server responded: {text}"
                )
            handle_response_status(status, text)
        return response_headers.get("ETag")

    async def delete_contact(self, contact_url: str, etag: Optional[str] = None) -> None:
        """Delete a vCard."""
        headers = {"authorization": self.auth_header}
        if etag:
            headers["If-Match"] = etag
        status, text, _ = await self._request("DELETE", contact_url, headers)
        if status in (200, 204):
            return
        if status == 404:
            raise HTTPException(
                status_code=404,
                detail=f"Contact not found at {contact_url}. The server responded: {text}"
            )
        if status == 405:
            raise HTTPException(
                status_code=405,
                detail=f"Cannot delete contact at this URL. The server responded: {text}"
            )
        handle_response_status(status, text)


class CalDavClient(BaseDavClient):
    """Async helper for CalDAV operations."""

    async def report_time_range(self, start_datetime: str, end_datetime: str) -> str:
        """Fetch events within a time window."""
        headers = create_caldav_request_headers(self.auth_header)
        xml_data = create_calendar_query_xml(start_datetime, end_datetime)
        status, text, _ = await self._request("REPORT", self.base_url, headers, data=xml_data)
        if status != 207:
            handle_caldav_response_status(status, text)
        return text

    async def get_event(self, event_url: str) -> Tuple[Optional[str], Optional[str]]:
        """Retrieve a single event."""
        headers = {
            "authorization": self.auth_header,
            "Content-Type": "text/calendar; charset=utf-8"
        }
        status, text, response_headers = await self._request("GET", event_url, headers)
        if status == 404:
            return None, None
        if status != 200:
            handle_caldav_response_status(status, text)
        return text, response_headers.get("ETag")

    async def create_event(self, event_url: str, ical_data: str) -> Optional[str]:
        """Create a VEVENT."""
        headers = create_caldav_event_headers(self.auth_header)
        status, text, response_headers = await self._request("PUT", event_url, headers, data=ical_data)
        if status not in (201, 204):
            handle_caldav_response_status(status, text)
        return response_headers.get("ETag")

    async def update_event(self, event_url: str, ical_data: str, etag: Optional[str] = None) -> Optional[str]:
        """Update an existing VEVENT."""
        headers = create_caldav_event_headers(self.auth_header)
        if etag:
            headers["If-Match"] = etag
        status, text, response_headers = await self._request("PUT", event_url, headers, data=ical_data)
        if status not in (200, 204):
            handle_caldav_response_status(status, text)
        return response_headers.get("ETag")

    async def delete_event(self, event_url: str, etag: Optional[str] = None) -> bool:
        """Delete a VEVENT, returning False if the server reports 404."""
        headers = {"authorization": self.auth_header}
        if etag:
            headers["If-Match"] = etag
        status, text, _ = await self._request("DELETE", event_url, headers)
        if status in (200, 204):
            return True
        if status == 404:
            return False
        handle_caldav_response_status(status, text)
        return True
