import uuid
from .conftest import client


def get_headers(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": f"{uuid.uuid4()}@ex.com", "password": "secret"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_notebook_crud(client):
    headers = get_headers(client)
    create = client.post(
        "/api/notebook/entries",
        json={"title": "Day1", "content": "Initial", "blocks": [{"type": "text", "text": "hello"}]},
        headers=headers,
    )
    assert create.status_code == 200
    data = create.json()
    entry_id = data["id"]
    assert data["title"] == "Day1"

    get_resp = client.get(f"/api/notebook/entries/{entry_id}", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == entry_id

    list_resp = client.get("/api/notebook/entries", headers=headers)
    assert any(e["id"] == entry_id for e in list_resp.json())

    upd = client.put(
        f"/api/notebook/entries/{entry_id}",
        json={"content": "Updated", "blocks": [{"type": "text", "text": "bye"}]},
        headers=headers,
    )
    assert upd.status_code == 200
    assert upd.json()["content"] == "Updated"
    assert upd.json()["blocks"][0]["text"] == "bye"

    del_resp = client.delete(f"/api/notebook/entries/{entry_id}", headers=headers)
    assert del_resp.status_code == 200
    list_after = client.get("/api/notebook/entries", headers=headers)
    assert all(e["id"] != entry_id for e in list_after.json())


def test_notebook_export(client):
    headers = get_headers(client)
    create = client.post(
        "/api/notebook/entries",
        json={"title": "Day2", "content": "Text"},
        headers=headers,
    )
    entry_id = create.json()["id"]
    resp = client.get(f"/api/notebook/entries/{entry_id}/export", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 0


def test_notebook_with_project_and_items(client):
    headers = get_headers(client)
    proj = client.post("/api/projects", json={"name": "P"}, headers=headers).json()
    item = client.post(
        "/api/inventory/items",
        json={"item_type": "sample", "name": "S"},
        headers=headers,
    ).json()
    entry = client.post(
        "/api/notebook/entries",
        json={"title": "Note", "content": "c", "project_id": proj["id"], "items": [item["id"]]},
        headers=headers,
    )
    assert entry.status_code == 200
    data = entry.json()
    assert data["project_id"] == proj["id"]
    assert item["id"] in data["items"]


def test_notebook_sign_and_versions(client):
    headers = get_headers(client)
    create = client.post(
        "/api/notebook/entries",
        json={"title": "Sig", "content": "v1", "blocks": [{"type": "text", "text": "v1"}]},
        headers=headers,
    )
    entry_id = create.json()["id"]
    client.put(
        f"/api/notebook/entries/{entry_id}",
        json={"content": "v2", "blocks": [{"type": "text", "text": "v2"}]},
        headers=headers,
    )
    versions = client.get(f"/api/notebook/entries/{entry_id}/versions", headers=headers).json()
    assert len(versions) == 2
    assert versions[0]["blocks"][0]["text"] == "v1"
    sign = client.post(f"/api/notebook/entries/{entry_id}/sign", headers=headers)
    assert sign.status_code == 200
    locked = client.put(
        f"/api/notebook/entries/{entry_id}",
        json={"content": "v3"},
        headers=headers,
    )
    assert locked.status_code == 400
    witness_headers = get_headers(client)
    witness = client.post(f"/api/notebook/entries/{entry_id}/witness", headers=witness_headers)
    assert witness.status_code == 200
