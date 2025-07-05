import uuid
from .conftest import client


def get_headers(client):
    resp = client.post(
        "/api/auth/register", json={"email": f"{uuid.uuid4()}@ex.com", "password": "secret"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_calendar_events(client):
    headers = get_headers(client)
    evt = client.post(
        "/api/calendar",
        json={"title": "Meeting", "start_time": "2025-07-02T10:00:00", "end_time": "2025-07-02T11:00:00"},
        headers=headers,
    )
    assert evt.status_code == 200
    event_id = evt.json()["id"]

    upd = client.put(
        f"/api/calendar/{event_id}",
        json={"description": "updated"},
        headers=headers,
    )
    assert upd.status_code == 200
    assert upd.json()["description"] == "updated"

    events = client.get("/api/calendar", headers=headers)
    assert any(e["id"] == event_id for e in events.json())

    del_resp = client.delete(f"/api/calendar/{event_id}", headers=headers)
    assert del_resp.status_code == 204
