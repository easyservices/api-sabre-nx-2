# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""Thin wrapper around the Events API endpoints used in manual tests."""

from typing import Any, Dict, Optional
import requests

from .config import TestSettings, get_test_settings


class EventsApiClient:
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

    def get_event(self, uid: str) -> requests.Response:
        return self._request("GET", f"/events/{uid}")

    def list_events(self, start_datetime: str, end_datetime: str) -> requests.Response:
        params = {"start_datetime": start_datetime, "end_datetime": end_datetime}
        return self._request("GET", "/events/", params=params)

    def create_event(self, payload: Dict[str, Any]) -> requests.Response:
        return self._request("POST", "/events/", json=payload)

    def update_event(self, uid: str, payload: Dict[str, Any]) -> requests.Response:
        return self._request("PUT", f"/events/{uid}", json=payload)

    def delete_event(self, uid: str) -> requests.Response:
        return self._request("DELETE", f"/events/{uid}")
