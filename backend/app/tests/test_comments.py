from .conftest import client
import uuid


def get_headers(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": f"{uuid.uuid4()}@ex.com", "password": "secret"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def create_item(client, headers):
    resp = client.post(
        "/api/inventory/items",
        json={"item_type": "sample", "name": "ItemA"},
        headers=headers,
    )
    assert resp.status_code == 200
    return resp.json()["id"]


def test_comment_crud(client):
    headers = get_headers(client)
    item_id = create_item(client, headers)

    create = client.post(
        "/api/comments/",
        json={"content": "First", "item_id": item_id},
        headers=headers,
    )
    assert create.status_code == 200
    data = create.json()
    comment_id = data["id"]
    assert data["content"] == "First"

    list_resp = client.get(
        "/api/comments/",
        params={"item_id": item_id},
        headers=headers,
    )
    assert any(c["id"] == comment_id for c in list_resp.json())

    upd = client.put(
        f"/api/comments/{comment_id}",
        json={"content": "Updated"},
        headers=headers,
    )
    assert upd.status_code == 200
    assert upd.json()["content"] == "Updated"

    del_resp = client.delete(f"/api/comments/{comment_id}", headers=headers)
    assert del_resp.status_code == 200
    after = client.get(
        "/api/comments/",
        params={"item_id": item_id},
        headers=headers,
    )
    assert all(c["id"] != comment_id for c in after.json())
