import uuid
from .conftest import client


def auth_headers(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": f"search{uuid.uuid4()}@example.com", "password": "secret"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_search_items(client):
    headers = auth_headers(client)
    client.post(
        "/api/inventory/items",
        json={"item_type": "plasmid", "name": "GFP Vector"},
        headers=headers,
    )
    client.post(
        "/api/inventory/items",
        json={"item_type": "plasmid", "name": "RFP Vector"},
        headers=headers,
    )

    resp = client.get("/api/search/items", params={"q": "GFP"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "GFP Vector"

