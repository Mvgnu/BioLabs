import uuid


def get_headers(client, email=None):
    email = email or f"{uuid.uuid4()}@ex.com"
    resp = client.post("/api/auth/register", json={"email": email, "password": "secret"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_follow_and_feed(client):
    h1 = get_headers(client)
    h2 = get_headers(client)

    # user2 creates a post
    resp = client.post("/api/community/posts", json={"content": "hello"}, headers=h2)
    assert resp.status_code == 200
    post_id = resp.json()["id"]

    # user1 follows user2
    uid2 = client.get("/api/users/me", headers=h2).json()["id"]
    f = client.post(f"/api/community/follow/{uid2}", headers=h1)
    assert f.status_code == 200

    feed = client.get("/api/community/feed", headers=h1)
    assert any(p["id"] == post_id for p in feed.json())

    # unfollow
    unf = client.delete(f"/api/community/follow/{uid2}", headers=h1)
    assert unf.status_code == 200

    feed2 = client.get("/api/community/feed", headers=h1)
    assert not feed2.json()


def test_list_posts(client):
    h = get_headers(client)
    resp = client.post("/api/community/posts", json={"content": "post"}, headers=h)
    assert resp.status_code == 200
    uid = client.get("/api/users/me", headers=h).json()["id"]
    posts = client.get("/api/community/posts", params={"user_id": uid}, headers=h)
    assert len(posts.json()) == 1


def test_report_and_resolve(client):
    h1 = get_headers(client)
    h2 = get_headers(client)
    post = client.post("/api/community/posts", json={"content": "bad"}, headers=h2).json()
    rep = client.post(
        f"/api/community/posts/{post['id']}/report",
        json={"reason": "spam"},
        headers=h1,
    )
    assert rep.status_code == 200
    rid = rep.json()["id"]
    reports = client.get("/api/community/reports", headers=h1).json()
    assert any(r["id"] == rid for r in reports)
    res = client.post(f"/api/community/reports/{rid}/resolve", headers=h1)
    assert res.status_code == 200


def test_like_and_unlike_post(client):
    h1 = get_headers(client)
    post = client.post("/api/community/posts", json={"content": "hi"}, headers=h1).json()
    resp = client.post(f"/api/community/posts/{post['id']}/like", headers=h1)
    assert resp.status_code == 200
    count = client.get(f"/api/community/posts/{post['id']}/likes", headers=h1).json()
    assert count == 1
    resp2 = client.delete(f"/api/community/posts/{post['id']}/like", headers=h1)
    assert resp2.status_code == 200
    count2 = client.get(f"/api/community/posts/{post['id']}/likes", headers=h1).json()
    assert count2 == 0
