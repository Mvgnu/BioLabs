from .conftest import client


def get_auth_headers(client, email="user@example.com"):
    resp = client.post("/api/auth/register", json={"email": email, "password": "secret"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_get_and_update_profile(client):
    headers = get_auth_headers(client)
    resp = client.get("/api/users/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == "user@example.com"

    update = {"full_name": "Tester", "phone_number": "123", "orcid_id": "0000-0001"}
    up_resp = client.put("/api/users/me", json=update, headers=headers)
    assert up_resp.status_code == 200
    updated = up_resp.json()
    assert updated["full_name"] == "Tester"
    assert updated["phone_number"] == "123"
    assert updated["orcid_id"] == "0000-0001"
