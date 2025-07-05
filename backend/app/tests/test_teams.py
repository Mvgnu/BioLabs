from .conftest import client


import uuid


def get_headers(client, email=None):
    email = email or f"user{uuid.uuid4()}@example.com"
    resp = client.post(
        "/api/auth/register", json={"email": email, "password": "secret"}
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_and_add_member(client):
    headers = get_headers(client)
    resp = client.post("/api/teams/", json={"name": "TeamA"}, headers=headers)
    assert resp.status_code == 200
    team_id = resp.json()["id"]

    get_headers(client, "member@example.com")
    add_resp = client.post(
        f"/api/teams/{team_id}/members",
        json={"email": "member@example.com"},
        headers=headers,
    )
    assert add_resp.status_code == 200
    data = add_resp.json()
    assert data["user"]["email"] == "member@example.com"


def test_non_owner_cannot_add_member(client):
    owner_headers = get_headers(client)
    resp = client.post("/api/teams/", json={"name": "T"}, headers=owner_headers)
    team_id = resp.json()["id"]

    member_headers = get_headers(client)
    fail = client.post(
        f"/api/teams/{team_id}/members",
        json={"email": "x@example.com"},
        headers=member_headers,
    )
    assert fail.status_code == 403
