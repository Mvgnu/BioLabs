from .conftest import client, ensure_auth_headers


def get_auth_headers(client, email="user@example.com"):
    headers, actual_email = ensure_auth_headers(client, email=email)
    return headers, actual_email


def test_get_and_update_profile(client):
    headers, email = get_auth_headers(client)
    resp = client.get("/api/users/me", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["email"] == email

    update = {"full_name": "Tester", "phone_number": "123", "orcid_id": "0000-0001"}
    up_resp = client.put("/api/users/me", json=update, headers=headers)
    assert up_resp.status_code == 200
    updated = up_resp.json()
    assert updated["full_name"] == "Tester"
    assert updated["phone_number"] == "123"
    assert updated["orcid_id"] == "0000-0001"
