from .conftest import client


def get_headers(client, email):
    resp = client.post("/api/auth/register", json={"email": email, "password": "secret"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_resource_share_flow(client):
    h1 = get_headers(client, "share1@example.com")
    h2 = get_headers(client, "share2@example.com")

    lab1 = client.post("/api/labs", json={"name": "LabA"}, headers=h1).json()
    lab2 = client.post("/api/labs", json={"name": "LabB"}, headers=h2).json()

    res = client.post("/api/schedule/resources", json={"name": "Scope"}, headers=h1)
    assert res.status_code == 200
    resource_id = res.json()["id"]

    share = client.post(
        "/api/resource-shares",
        json={"resource_id": resource_id, "to_lab": lab2["id"]},
        headers=h1,
    )
    assert share.status_code == 200
    share_id = share.json()["id"]

    lst = client.get("/api/resource-shares", headers=h2).json()
    assert any(s["id"] == share_id for s in lst)

    acc = client.post(f"/api/resource-shares/{share_id}/accept", headers=h2)
    assert acc.status_code == 200
    assert acc.json()["status"] == "accepted"
