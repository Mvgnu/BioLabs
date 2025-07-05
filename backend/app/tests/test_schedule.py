import uuid
from .conftest import client


def get_headers(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": f"{uuid.uuid4()}@ex.com", "password": "secret"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_booking_conflict(client):
    headers = get_headers(client)
    res = client.post(
        "/api/schedule/resources",
        json={"name": "Microscope"},
        headers=headers,
    )
    assert res.status_code == 200
    resource_id = res.json()["id"]

    b1 = client.post(
        "/api/schedule/bookings",
        json={
            "resource_id": resource_id,
            "start_time": "2025-07-02T10:00:00",
            "end_time": "2025-07-02T11:00:00",
        },
        headers=headers,
    )
    assert b1.status_code == 200

    conflict = client.post(
        "/api/schedule/bookings",
        json={
            "resource_id": resource_id,
            "start_time": "2025-07-02T10:30:00",
            "end_time": "2025-07-02T11:30:00",
        },
        headers=headers,
    )
    assert conflict.status_code == 400

    list_resp = client.get(
        "/api/schedule/bookings",
        params={"resource_id": resource_id},
        headers=headers,
    )
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert len(data) == 1
