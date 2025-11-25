# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""Helper client for Contacts API endpoints used by manual CLI tests."""

from typing import Any, Dict, Optional
import requests

from .config import TestSettings, get_test_settings


class ContactsApiClient:
    def __init__(self, settings: Optional[TestSettings] = None):
        self.settings = settings or get_test_settings()

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": self.settings.auth_header(),
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> requests.Response:
        url = f"{self.settings.api_base_url}{path}"
        return requests.request(method, url, headers=self._headers(), params=params, json=json)

    def list_contacts(self) -> requests.Response:
        return self._request("GET", "/contacts")

    def search_contacts(self, criteria: Dict[str, Any]) -> requests.Response:
        return self._request("POST", "/contacts/search", json=criteria)

    def create_contact(self, payload: Dict[str, Any]) -> requests.Response:
        return self._request("POST", "/contacts", json=payload)

    def update_contact(self, uid: str, payload: Dict[str, Any]) -> requests.Response:
        return self._request("PUT", f"/contacts/{uid}", json=payload)

    def delete_contact(self, uid: str) -> requests.Response:
        return self._request("DELETE", f"/contacts/{uid}")

    def get_contact(self, uid: str) -> requests.Response:
        return self._request("GET", f"/contacts/{uid}")
