import uuid
from .conftest import client


def get_headers(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": f"{uuid.uuid4()}@ex.com", "password": "secret"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_forum_flow(client):
    headers = get_headers(client)
    th = client.post("/api/forum/threads", json={"title": "Test"}, headers=headers)
    assert th.status_code == 200
    tid = th.json()["id"]
    post = client.post(
        f"/api/forum/threads/{tid}/posts",
        json={"thread_id": tid, "content": "Hello"},
        headers=headers,
    )
    assert post.status_code == 200
    lst = client.get(f"/api/forum/threads/{tid}/posts", headers=headers)
    assert any(p["id"] == post.json()["id"] for p in lst.json())
