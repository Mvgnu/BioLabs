import uuid
from .conftest import client


def get_headers(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": f"{uuid.uuid4()}@ex.com", "password": "secret"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_troubleshooting_flow(client):
    headers = get_headers(client)
    create = client.post(
        "/api/troubleshooting/articles",
        json={"title": "PCR Issues", "category": "PCR", "content": "Check MgCl2"},
        headers=headers,
    )
    assert create.status_code == 200
    art_id = create.json()["id"]

    list_resp = client.get("/api/troubleshooting/articles", headers=headers)
    assert any(a["id"] == art_id for a in list_resp.json())

    upd = client.put(
        f"/api/troubleshooting/articles/{art_id}",
        json={"content": "Adjust MgCl2 concentration"},
        headers=headers,
    )
    assert upd.status_code == 200
    assert upd.json()["content"] == "Adjust MgCl2 concentration"

    mark = client.post(
        f"/api/troubleshooting/articles/{art_id}/success", headers=headers
    )
    assert mark.status_code == 200
    assert mark.json()["success_count"] == 1
