import uuid
from .conftest import client


def get_headers(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": f"{uuid.uuid4()}@ex.com", "password": "secret"},
    )
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    me = client.get("/api/users/me", headers=headers)
    user_id = me.json()["id"]
    return headers | {"user_id": user_id}


def test_equipment_flow(client):
    headers = get_headers(client)
    eq = client.post(
        "/api/equipment/devices",
        json={"name": "Thermocycler", "eq_type": "pcr"},
        headers=headers,
    )
    assert eq.status_code == 200
    eq_id = eq.json()["id"]

    upd = client.put(
        f"/api/equipment/devices/{eq_id}",
        json={"status": "online"},
        headers=headers,
    )
    assert upd.status_code == 200
    assert upd.json()["status"] == "online"

    reading = client.post(
        f"/api/equipment/devices/{eq_id}/readings",
        json={"data": {"temp": 95}},
        headers=headers,
    )
    assert reading.status_code == 200

    lst = client.get(
        f"/api/equipment/devices/{eq_id}/readings",
        headers=headers,
    )
    assert lst.status_code == 200
    assert len(lst.json()) == 1


def test_equipment_ops(client):
    headers = get_headers(client)
    eq = client.post(
        "/api/equipment/devices",
        json={"name": "Centrifuge", "eq_type": "spin"},
        headers=headers,
    )
    eq_id = eq.json()["id"]

    maint = client.post(
        "/api/equipment/maintenance",
        json={"equipment_id": eq_id, "due_date": "2030-01-01T00:00:00Z"},
        headers=headers,
    )
    assert maint.status_code == 200

    s = client.post(
        "/api/equipment/sops",
        json={"title": "Use", "content": "steps"},
        headers=headers,
    )
    sop_id = s.json()["id"]

    tr = client.post(
        "/api/equipment/training",
        json={
            "user_id": headers["user_id"],
            "sop_id": sop_id,
            "equipment_id": eq_id,
            "trained_by": headers["user_id"],
        },
        headers=headers,
    )
    assert tr.status_code == 200
