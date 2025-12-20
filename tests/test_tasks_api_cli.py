from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Dict

import pytest
import requests

from src.common.config import UsersSettings
from src.common.sec import gen_basic_auth_header
from src.nextcloud.config import get_api_proxy_url

settings = UsersSettings()
NEXTCLOUD_INTRANET_URL = get_api_proxy_url()
CALENDAR_NAME = settings.USERS["test4me"].NEXTCLOUD_CALENDAR


def _auth_headers() -> Dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": gen_basic_auth_header(
            settings.USERS["test4me"].NEXTCLOUD_USERNAME,
            settings.USERS["test4me"].NEXTCLOUD_PASSWORD,
        ),
    }


def _skip_if_forbidden(resp: requests.Response) -> None:
    """Skip tasks tests gracefully when backend rejects VTODO writes."""
    text = (resp.text or "").lower()
    if resp.status_code in (403, 503) and ("authorizationerror" in text or "forbidden" in text):
        pytest.skip(f"Tasks backend forbids VTODO operations: {resp.status_code} {resp.text}")


def _calendar_params(base: Dict | None = None) -> Dict:
    params = dict(base or {})
    if CALENDAR_NAME:
        params["calendar_name"] = CALENDAR_NAME
    return params


def _sample_task_payload() -> Dict:
    now = datetime.now().replace(microsecond=0)
    due = now + timedelta(days=1)
    return {
        "uid": str(uuid.uuid4()),
        "summary": "Test Task from API Client",
        "description": "This is a test task created by the API client",
        "start": now.isoformat(),
        "due": due.isoformat(),
        "all_day": False,
        "status": "NEEDS-ACTION",
        "percent_complete": 0,
        "categories": ["TEST", "API", "CLIENT"],
    }


def _create_task_on_server() -> Dict:
    response = requests.post(
        f"{NEXTCLOUD_INTRANET_URL}/tasks/",
        json=_sample_task_payload(),
        headers=_auth_headers(),
        params=_calendar_params(),
    )
    if response.status_code not in (200, 201):
        _skip_if_forbidden(response)
        response.raise_for_status()
    return response.json()


def _delete_task(uid: str) -> None:
    response = requests.delete(
        f"{NEXTCLOUD_INTRANET_URL}/tasks/{uid}",
        headers=_auth_headers(),
    )
    if response.status_code not in (200, 204, 404):
        response.raise_for_status()


def test_get_task_by_uid(is_debug: bool = False):
    created_task = _create_task_on_server()
    task_uid = created_task["uid"]

    response = requests.get(
        f"{NEXTCLOUD_INTRANET_URL}/tasks/{task_uid}",
        headers=_auth_headers(),
        params=_calendar_params(),
    )

    if is_debug:
        print("\n### TEST GET TASK BY UID ###")
        print(f"Status Code: {response.status_code}")

    assert response.status_code == 200, (
        f"Expected 200 when retrieving task by UID, got {response.status_code}: {response.text}"
    )

    result = response.json()
    assert result.get("uid") == task_uid
    _delete_task(task_uid)


def test_get_tasks_by_time_range(is_debug: bool = False):
    now = datetime.now().replace(microsecond=0)
    start_datetime = now.isoformat()
    end_datetime = (now + timedelta(days=7)).isoformat()

    response = requests.get(
        f"{NEXTCLOUD_INTRANET_URL}/tasks/",
        params=_calendar_params(
            {
                "start_datetime": start_datetime,
                "end_datetime": end_datetime,
            }
        ),
        headers=_auth_headers(),
    )

    if is_debug:
        print("\n### TEST GET TASKS BY TIME RANGE ###")
        print(f"Status Code: {response.status_code}")

    assert response.status_code == 200, (
        f"Expected 200 when retrieving tasks range, got {response.status_code}: {response.text}"
    )

    results = response.json()
    assert isinstance(results, list)


def test_create_task(is_debug: bool = False):
    task_data = _sample_task_payload()
    response = requests.post(
        f"{NEXTCLOUD_INTRANET_URL}/tasks/",
        json=task_data,
        headers=_auth_headers(),
        params=_calendar_params(),
    )

    if is_debug:
        print("\n### TEST CREATE TASK ###")
        print(f"Status Code: {response.status_code}")

    if response.status_code not in (200, 201):
        _skip_if_forbidden(response)
    assert response.status_code in (200, 201), (
        f"Expected 200/201 when creating task, got {response.status_code}: {response.text}"
    )

    result = response.json()
    assert result.get("uid") == task_data["uid"]
    _delete_task(result["uid"])


def test_update_task(is_debug: bool = False):
    created_task = _create_task_on_server()
    task_uid = created_task["uid"]

    created_task["summary"] = f"{created_task['summary']} (API Updated)"
    created_task["description"] = (
        f"{created_task.get('description') or ''}\nUpdated via API on {datetime.now().isoformat()}"
    )
    created_task.setdefault("categories", []).append("API-UPDATED")
    created_task["percent_complete"] = 50

    response = requests.put(
        f"{NEXTCLOUD_INTRANET_URL}/tasks/{task_uid}",
        json=created_task,
        headers=_auth_headers(),
        params=_calendar_params(),
    )

    if is_debug:
        print("\n### TEST UPDATE TASK ###")
        print(f"Status Code: {response.status_code}")

    if response.status_code != 200:
        _skip_if_forbidden(response)
    assert response.status_code == 200, (
        f"Expected 200 when updating task, got {response.status_code}: {response.text}"
    )

    result = response.json()
    assert result.get("summary", "").endswith("(API Updated)")
    _delete_task(task_uid)


def test_delete_task(is_debug: bool = False):
    created_task = _create_task_on_server()
    task_uid = created_task["uid"]

    response = requests.delete(
        f"{NEXTCLOUD_INTRANET_URL}/tasks/{task_uid}",
        headers=_auth_headers(),
        params=_calendar_params(),
    )

    if is_debug:
        print("\n### TEST DELETE TASK ###")
        print(f"Status Code: {response.status_code}")

    if response.status_code not in (200, 204):
        _skip_if_forbidden(response)
    assert response.status_code == 204, (
        f"Expected 204 when deleting task, got {response.status_code}: {response.text}"
    )


def test_list_calendars(is_debug: bool = False):
    response = requests.get(
        f"{NEXTCLOUD_INTRANET_URL}/tasks/calendars",
        headers=_auth_headers(),
    )

    if is_debug:
        print("\n### TEST LIST CALENDARS ###")
        print(f"Status Code: {response.status_code}")
        print(f"Body: {response.text}")

    assert response.status_code == 200, (
        f"Expected 200 when listing calendars, got {response.status_code}: {response.text}"
    )
    result = response.json()
    assert isinstance(result, list), "Calendars response should be a list"
    if result:
        assert "url" in result[0], "Calendar entry should include url"


def test_list_calendars_cache_headers(is_debug: bool = False):
    first = requests.get(f"{NEXTCLOUD_INTRANET_URL}/tasks/calendars", headers=_auth_headers())
    second = requests.get(f"{NEXTCLOUD_INTRANET_URL}/tasks/calendars", headers=_auth_headers())

    assert first.status_code == 200, f"First calendars call failed: {first.status_code} {first.text}"
    assert second.status_code == 200, f"Second calendars call failed: {second.status_code} {second.text}"

    assert "X-Cache" in first.headers and "X-Cache" in second.headers
    assert second.headers.get("X-Cache") == "HIT"


def test_list_calendars_auth_failure():
    bad_headers = {
        "Authorization": gen_basic_auth_header("wrong", "wrong"),
        "Content-Type": "application/json",
    }
    resp = requests.get(f"{NEXTCLOUD_INTRANET_URL}/tasks/calendars", headers=bad_headers)
    assert resp.status_code == 401


def test_missing_calendar_returns_404():
    now = datetime.now().replace(microsecond=0)
    start_datetime = now.isoformat()
    end_datetime = (now + timedelta(days=1)).isoformat()
    resp = requests.get(
        f"{NEXTCLOUD_INTRANET_URL}/tasks/",
        params={
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
            "calendar_name": "does-not-exist-xyz",
        },
        headers=_auth_headers(),
    )
    assert resp.status_code == 404, f"Expected 404 for missing calendar, got {resp.status_code}: {resp.text}"
