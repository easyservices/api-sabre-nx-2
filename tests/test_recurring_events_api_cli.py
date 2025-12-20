from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Dict, List

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


def _calendar_params(base: Dict | None = None) -> Dict:
    params = dict(base or {})
    if CALENDAR_NAME:
        params["calendar_name"] = CALENDAR_NAME
    return params


def _sample_recurring_event_payload(count: int = 3, interval: int = 1) -> Dict:
    start = datetime.now().replace(microsecond=0, second=0)
    end = start + timedelta(hours=1)
    return {
        "uid": str(uuid.uuid4()),
        "summary": "Recurring Event (CLI)",
        "description": "API CLI recurring test",
        "location": "Virtual",
        "start": start.isoformat(),
        "end": end.isoformat(),
        "all_day": False,
        "recurrence": f"FREQ=DAILY;INTERVAL={interval};COUNT={count}",
        "categories": ["TEST", "RECURRENCE"],
    }


def _create_recurring_event(count: int = 3) -> Dict:
    payload = _sample_recurring_event_payload(count=count)
    response = requests.post(
        f"{NEXTCLOUD_INTRANET_URL}/events/",
        json=payload,
        headers=_auth_headers(),
        params=_calendar_params(),
    )
    response.raise_for_status()
    return response.json()


def _delete_event(uid: str) -> None:
    response = requests.delete(
        f"{NEXTCLOUD_INTRANET_URL}/events/{uid}",
        headers=_auth_headers(),
        params=_calendar_params(),
    )
    if response.status_code not in (200, 204, 404):
        response.raise_for_status()


def _get_instances(uid: str, window_days: int = 7) -> List[Dict]:
    start = datetime.now().replace(microsecond=0, second=0)
    end = start + timedelta(days=window_days)
    response = requests.get(
        f"{NEXTCLOUD_INTRANET_URL}/events/recurring/{uid}/instances",
        headers=_auth_headers(),
        params=_calendar_params(
            {
                "start_datetime": start.isoformat(),
                "end_datetime": end.isoformat(),
            }
        ),
    )
    response.raise_for_status()
    return response.json()


def test_build_recurrence_rule_cli(is_debug: bool = False):
    payload = {
        "friendly": {
            "frequency": "WEEKLY",
            "interval": 2,
            "count": 4,
            "byweekday": ["MO", "WE"],
        }
    }
    resp = requests.post(
        f"{NEXTCLOUD_INTRANET_URL}/events/recurring/rule",
        json=payload,
        headers=_auth_headers(),
    )
    if is_debug:
        print("\n### TEST BUILD RECURRENCE RULE ###")
        print(f"Status Code: {resp.status_code}")
        print(resp.text)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert "rrule" in body
    assert "FREQ=WEEKLY" in body["rrule"]
    assert "BYDAY=MO,WE" in body["rrule"]


def test_preview_recurrence_cli(is_debug: bool = False):
    start = datetime.now().replace(microsecond=0, second=0)
    end = start + timedelta(hours=1)
    payload = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "all_day": False,
        "friendly": {
            "frequency": "DAILY",
            "interval": 1,
            "count": 3,
        },
        "max_occurrences": 5,
    }
    resp = requests.post(
        f"{NEXTCLOUD_INTRANET_URL}/events/recurring/preview",
        json=payload,
        headers=_auth_headers(),
    )
    if is_debug:
        print("\n### TEST PREVIEW RECURRENCE ###")
        print(f"Status Code: {resp.status_code}")
        print(resp.text)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert len(body.get("occurrences", [])) == 3
    assert body["occurrences"][0]["recurrence_id"]


def test_expand_recurring_instances_cli(is_debug: bool = False):
    created = _create_recurring_event(count=3)
    uid = created["uid"]
    try:
        instances = _get_instances(uid, window_days=5)
        if is_debug:
            print("\n### TEST EXPAND INSTANCES ###")
            print(instances)
        assert len(instances) >= 3
        assert all(inst.get("source_uid") == uid for inst in instances)
    finally:
        _delete_event(uid)


def test_upsert_recurrence_exception_cli(is_debug: bool = False):
    created = _create_recurring_event(count=3)
    uid = created["uid"]
    base_instances = _get_instances(uid, window_days=5)
    target = base_instances[1]["recurrence_id"]
    try:
        payload = {
            "recurrence_id": target,
            "summary": "Exception Override",
            "location": "Exception Location",
        }
        resp = requests.post(
            f"{NEXTCLOUD_INTRANET_URL}/events/recurring/{uid}/exception",
            json=payload,
            headers=_auth_headers(),
            params=_calendar_params(),
        )
        if is_debug:
            print("\n### TEST UPSERT EXCEPTION ###")
            print(f"Status Code: {resp.status_code}")
            print(resp.text)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert body.get("recurrence_id") == target
        assert body.get("summary") == "Exception Override"

        instances = _get_instances(uid, window_days=5)
        flagged = [inst for inst in instances if inst["recurrence_id"] == target]
        assert flagged and flagged[0]["overrides_applied"] is True
    finally:
        _delete_event(uid)


def test_skip_recurrence_instances_cli(is_debug: bool = False):
    created = _create_recurring_event(count=4)
    uid = created["uid"]
    try:
        instances_before = _get_instances(uid, window_days=7)
        to_skip = instances_before[1]["recurrence_id"]
        payload = {"recurrence_ids": [to_skip]}
        resp = requests.post(
            f"{NEXTCLOUD_INTRANET_URL}/events/recurring/{uid}/skip",
            json=payload,
            headers=_auth_headers(),
            params=_calendar_params(),
        )
        if is_debug:
            print("\n### TEST SKIP INSTANCES ###")
            print(f"Status Code: {resp.status_code}")
            print(resp.text)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        instances_after = _get_instances(uid, window_days=7)
        skipped_ids = [inst["recurrence_id"] for inst in instances_after]
        assert to_skip not in skipped_ids, "Skipped recurrence should not appear after EXDATE"
        assert len(instances_after) == len(instances_before) - 1
    finally:
        _delete_event(uid)
