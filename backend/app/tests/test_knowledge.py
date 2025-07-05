import uuid
from .conftest import client


def get_headers(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": f"{uuid.uuid4()}@ex.com", "password": "secret"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_knowledge_crud(client):
    headers = get_headers(client)
    resp = client.post(
        "/api/knowledge/articles",
        json={"title": "Cloning tips", "content": "Use fresh cells", "tags": ["cloning"]},
        headers=headers,
    )
    assert resp.status_code == 200
    art_id = resp.json()["id"]

    list_resp = client.get("/api/knowledge/articles", headers=headers)
    assert any(a["id"] == art_id for a in list_resp.json())

    upd = client.put(
        f"/api/knowledge/articles/{art_id}",
        json={"content": "Use competent cells"},
        headers=headers,
    )
    assert upd.status_code == 200
    assert upd.json()["content"] == "Use competent cells"

    del_resp = client.delete(f"/api/knowledge/articles/{art_id}", headers=headers)
    assert del_resp.status_code == 200


def test_article_comments(client):
    headers = get_headers(client)
    art = client.post(
        "/api/knowledge/articles",
        json={"title": "Tips", "content": "Use buffer", "is_public": True},
        headers=headers,
    ).json()
    c = client.post(
        "/api/comments/",
        json={"content": "Great", "knowledge_article_id": art["id"]},
        headers=headers,
    )
    assert c.status_code == 200
    cid = c.json()["id"]
    listed = client.get(
        "/api/comments/",
        params={"article_id": art["id"]},
        headers=headers,
    )
    assert any(cm["id"] == cid for cm in listed.json())


def test_article_stars(client):
    headers = get_headers(client)
    art = client.post(
        "/api/knowledge/articles",
        json={"title": "Star", "content": "text"},
        headers=headers,
    ).json()

    resp = client.post(f"/api/knowledge/articles/{art['id']}/star", headers=headers)
    assert resp.status_code == 200
    count = client.get(f"/api/knowledge/articles/{art['id']}/stars", headers=headers).json()
    assert count["count"] == 1

    # starring again has no effect
    client.post(f"/api/knowledge/articles/{art['id']}/star", headers=headers)
    count = client.get(f"/api/knowledge/articles/{art['id']}/stars", headers=headers).json()
    assert count["count"] == 1

    client.delete(f"/api/knowledge/articles/{art['id']}/star", headers=headers)
    count = client.get(f"/api/knowledge/articles/{art['id']}/stars", headers=headers).json()
    assert count["count"] == 0
