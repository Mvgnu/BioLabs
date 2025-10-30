from .conftest import client, ensure_auth_headers
import uuid


def get_headers(client, email):
    headers, _ = ensure_auth_headers(client, email=email)
    return headers


def test_lab_connection_flow(client):
    h1 = get_headers(client, "lab1@example.com")
    h2 = get_headers(client, "lab2@example.com")

    lab1 = client.post("/api/labs", json={"name": "Lab1"}, headers=h1).json()
    lab2 = client.post("/api/labs", json={"name": "Lab2"}, headers=h2).json()

    req = client.post(f"/api/labs/{lab1['id']}/connections", json={"target_lab": lab2['id']}, headers=h1)
    assert req.status_code == 200
    conn_id = req.json()["id"]

    lst = client.get("/api/labs/connections", headers=h1).json()
    assert any(c["id"] == conn_id for c in lst)

    acc = client.post(f"/api/labs/connections/{conn_id}/accept", headers=h2)
    assert acc.status_code == 200
    assert acc.json()["status"] == "accepted"
