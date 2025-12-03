import json
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException, status
from fastapi.security import HTTPBasicCredentials

from src.common import audit as audit_mod
from src.models.contact import Contact
from src.models.event import Event
from src.nextcloud import contacts as contacts_mod
from src.nextcloud import events as events_mod
from src.nextcloud.libs.carddav_helpers import contact_to_vcard
from src.nextcloud.libs.caldav_helpers import event_to_ical


@pytest.mark.asyncio
async def test_contact_update_conflict_returns_latest_payload(monkeypatch, tmp_path):
    audit_file = tmp_path / "contact_audit.log"
    monkeypatch.setattr(audit_mod, "AUDIT_LOG_PATH", audit_file)

    async def fake_auth(credentials):
        return {"id": "demo"}

    monkeypatch.setattr(contacts_mod, "authenticate_with_nextcloud", fake_auth)

    initial = Contact(uid="contact-1", full_name="Alice Original")
    initial_vcard = contact_to_vcard(initial)
    initial_etag = '"etag-1"'

    updated = Contact(uid="contact-1", full_name="Alice Server Copy")
    updated_vcard = contact_to_vcard(updated)
    updated_etag = '"etag-2"'

    state = {"get": 0, "update": 0}
    get_sequence = [
        (initial_vcard, initial_etag),
        (updated_vcard, updated_etag),
        (updated_vcard, updated_etag),
    ]
    update_behaviors = [
        {"type": "success", "etag": updated_etag},
        {"type": "conflict"},
    ]

    class StubCardDavClient:
        def __init__(self, base_url, auth_header):
            self.base_url = base_url if base_url.endswith('/') else f"{base_url}/"
            self.auth_header = auth_header

        def build_url(self, relative_path: str) -> str:
            return f"{self.base_url}{relative_path.lstrip('/')}"

        async def get_contact(self, contact_url: str):
            idx = min(state["get"], len(get_sequence) - 1)
            state["get"] += 1
            return get_sequence[idx]

        async def update_contact(self, contact_url: str, vcard_data: str, etag: str = None):
            behavior = update_behaviors[state["update"]]
            state["update"] += 1
            if behavior["type"] == "success":
                return behavior["etag"]
            raise HTTPException(status_code=status.HTTP_412_PRECONDITION_FAILED, detail="conflict")

    monkeypatch.setattr(contacts_mod, "CardDavClient", StubCardDavClient)

    credentials = HTTPBasicCredentials(username="user", password="pass")
    first_payload = Contact(uid="contact-1", full_name="Alice First Attempt", etag=initial_etag)
    result = await contacts_mod.update_contact(credentials, first_payload)
    assert result.etag == updated_etag

    stale_payload = Contact(uid="contact-1", full_name="Alice Stale Attempt", etag=initial_etag)
    with pytest.raises(HTTPException) as exc_info:
        await contacts_mod.update_contact(credentials, stale_payload)

    assert exc_info.value.status_code == status.HTTP_412_PRECONDITION_FAILED
    detail = exc_info.value.detail
    assert detail["current"]["full_name"] == updated.full_name
    assert detail["current"]["etag"] == updated_etag

    entries = [json.loads(line) for line in audit_file.read_text().splitlines() if line.strip()]
    assert entries[0]["action"] == "update"
    assert entries[1]["action"] == "conflict"
    assert entries[1]["before"]["etag"] == updated_etag
    assert entries[1]["after"]["full_name"] == stale_payload.full_name


@pytest.mark.asyncio
async def test_event_update_conflict_surfaces_current_payload(monkeypatch, tmp_path):
    audit_file = tmp_path / "event_audit.log"
    monkeypatch.setattr(audit_mod, "AUDIT_LOG_PATH", audit_file)

    async def fake_auth(credentials):
        return {"id": "demo"}

    monkeypatch.setattr(events_mod, "authenticate_with_nextcloud", fake_auth)

    now = datetime.now()
    base_event = Event(
        uid="event-1",
        summary="Planning",
        start=now.isoformat(timespec="seconds"),
        end=(now + timedelta(hours=1)).isoformat(timespec="seconds"),
    )
    base_ical = event_to_ical(base_event)
    base_etag = '"etag-10"'

    server_event = Event(
        uid="event-1",
        summary="Planning Updated",
        start=now.isoformat(timespec="seconds"),
        end=(now + timedelta(hours=1)).isoformat(timespec="seconds"),
    )
    server_ical = event_to_ical(server_event)
    server_etag = '"etag-11"'

    state = {"get": 0, "update": 0}
    get_sequence = [
        (base_ical, base_etag),
        (server_ical, server_etag),
        (server_ical, server_etag),
    ]
    update_behaviors = [
        {"type": "success", "etag": server_etag},
        {"type": "conflict"},
    ]

    class StubCalDavClient:
        def __init__(self, base_url, auth_header):
            self.base_url = base_url if base_url.endswith('/') else f"{base_url}/"
            self.auth_header = auth_header

        def build_url(self, relative_path: str) -> str:
            return f"{self.base_url}{relative_path.lstrip('/')}"

        async def get_event(self, event_url: str):
            idx = min(state["get"], len(get_sequence) - 1)
            state["get"] += 1
            return get_sequence[idx]

        async def update_event(self, event_url: str, ical_data: str, etag: str = None):
            behavior = update_behaviors[state["update"]]
            state["update"] += 1
            if behavior["type"] == "success":
                return behavior["etag"]
            raise HTTPException(status_code=status.HTTP_412_PRECONDITION_FAILED, detail="conflict")

        async def delete_event(self, event_url: str, etag: str = None):
            return True

    monkeypatch.setattr(events_mod, "CalDavClient", StubCalDavClient)

    credentials = HTTPBasicCredentials(username="user", password="pass")
    first_payload = Event(
        uid="event-1",
        summary="Planning First Attempt",
        start=now.isoformat(timespec="seconds"),
        end=(now + timedelta(hours=1)).isoformat(timespec="seconds"),
        etag=base_etag,
    )
    result = await events_mod.update_event(credentials, first_payload)
    assert result.etag == server_etag

    stale_payload = Event(
        uid="event-1",
        summary="Planning Second Attempt",
        start=now.isoformat(timespec="seconds"),
        end=(now + timedelta(hours=1)).isoformat(timespec="seconds"),
        etag=base_etag,
    )

    with pytest.raises(HTTPException) as exc_info:
        await events_mod.update_event(credentials, stale_payload)

    assert exc_info.value.status_code == status.HTTP_412_PRECONDITION_FAILED
    detail = exc_info.value.detail
    assert detail["current"]["summary"] == server_event.summary
    assert detail["current"]["etag"] == server_etag

    entries = [json.loads(line) for line in audit_file.read_text().splitlines() if line.strip()]
    assert entries[0]["action"] == "update"
    assert entries[1]["action"] == "conflict"
    assert entries[1]["before"]["etag"] == server_etag
    assert entries[1]["after"]["summary"] == stale_payload.summary
