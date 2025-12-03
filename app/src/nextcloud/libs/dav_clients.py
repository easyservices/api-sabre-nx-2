"""Utility clients for CardDAV and CalDAV network interactions."""

import aiohttp
from fastapi import HTTPException
from typing import Dict, Optional, Tuple

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


class BaseDavClient:
    """Shared functionality for DAV clients."""

    def __init__(self, base_url: str, auth_header: str) -> None:
        self.base_url = base_url if base_url.endswith('/') else f"{base_url}/"
        self.auth_header = auth_header

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
    ) -> Tuple[int, str]:
        """Execute an HTTP request and return the status/text pair."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=headers, data=data) as response:
                    text = await response.text()
                    return response.status, text
        except aiohttp.ClientError as exc:
            raise HTTPException(status_code=500, detail=f"{API_ERR_CONNECTION_ERROR}: {str(exc)}") from exc


class CardDavClient(BaseDavClient):
    """Async helper for CardDAV operations."""

    async def report_addressbook(self) -> str:
        """Fetch all contacts via REPORT."""
        headers = create_request_headers(self.auth_header)
        xml_data = create_request_xml()
        status, text = await self._request("REPORT", self.base_url, headers, data=xml_data)
        handle_response_status(status, text)
        return text

    async def search_addressbook(self, criteria: Dict[str, str], search_type: str) -> str:
        """Execute a REPORT with filters."""
        headers = create_request_headers(self.auth_header)
        xml_data = create_search_request_xml(criteria, search_type)
        status, text = await self._request("REPORT", self.base_url, headers, data=xml_data)
        handle_response_status(status, text)
        return text

    async def get_contact(self, contact_url: str) -> Optional[str]:
        """Retrieve a single vCard."""
        headers = {"authorization": self.auth_header}
        status, text = await self._request("GET", contact_url, headers)
        if status == 404:
            return None
        if status != 200:
            handle_response_status(status, text)
        return text

    async def create_contact(self, contact_url: str, vcard_data: str) -> None:
        """Create a contact via PUT."""
        headers = create_vcard_headers(self.auth_header)
        status, text = await self._request("PUT", contact_url, headers, data=vcard_data)
        if status not in (201, 204):
            if status == 405:
                raise HTTPException(
                    status_code=405,
                    detail=f"Cannot create contact at this URL. The server responded: {text}"
                )
            handle_response_status(status, text)

    async def update_contact(self, contact_url: str, vcard_data: str) -> None:
        """Update an existing contact."""
        headers = create_vcard_headers(self.auth_header)
        status, text = await self._request("PUT", contact_url, headers, data=vcard_data)
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

    async def delete_contact(self, contact_url: str) -> None:
        """Delete a vCard."""
        headers = {"authorization": self.auth_header}
        status, text = await self._request("DELETE", contact_url, headers)
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
        status, text = await self._request("REPORT", self.base_url, headers, data=xml_data)
        if status != 207:
            handle_caldav_response_status(status, text)
        return text

    async def get_event(self, event_url: str) -> Optional[str]:
        """Retrieve a single event."""
        headers = {
            "authorization": self.auth_header,
            "Content-Type": "text/calendar; charset=utf-8"
        }
        status, text = await self._request("GET", event_url, headers)
        if status == 404:
            return None
        if status != 200:
            handle_caldav_response_status(status, text)
        return text

    async def create_event(self, event_url: str, ical_data: str) -> None:
        """Create a VEVENT."""
        headers = create_caldav_event_headers(self.auth_header)
        status, text = await self._request("PUT", event_url, headers, data=ical_data)
        if status not in (201, 204):
            handle_caldav_response_status(status, text)

    async def update_event(self, event_url: str, ical_data: str) -> None:
        """Update an existing VEVENT."""
        headers = create_caldav_event_headers(self.auth_header)
        status, text = await self._request("PUT", event_url, headers, data=ical_data)
        if status not in (200, 204):
            handle_caldav_response_status(status, text)

    async def delete_event(self, event_url: str) -> bool:
        """Delete a VEVENT, returning False if the server reports 404."""
        headers = {"authorization": self.auth_header}
        status, text = await self._request("DELETE", event_url, headers)
        if status in (200, 204):
            return True
        if status == 404:
            return False
        handle_caldav_response_status(status, text)
        return True
