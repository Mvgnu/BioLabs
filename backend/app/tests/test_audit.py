import uuid
from .conftest import client


def get_headers(client):
    resp = client.post("/api/auth/register", json={"email": f"{uuid.uuid4()}@ex.com", "password": "secret"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_audit_log_item_creation(client):
    headers = get_headers(client)
    item = client.post("/api/inventory/items", json={"item_type": "sample", "name": "A"}, headers=headers).json()
    logs = client.get("/api/audit/", headers=headers)
    assert logs.status_code == 200
    data = logs.json()
    assert any(l["action"] == "create_item" and l["target_id"] == item["id"] for l in data)


def test_audit_report(client):
    headers = get_headers(client)
    client.post(
        "/api/inventory/items",
        json={"item_type": "sample", "name": "A"},
        headers=headers,
    )
    params = {
        "start": "2000-01-01T00:00:00",
        "end": "2100-01-01T00:00:00",
    }
    resp = client.get("/api/audit/report", headers=headers, params=params)
    assert resp.status_code == 200
    data = resp.json()
    assert any(r["action"] == "create_item" and r["count"] >= 1 for r in data)
