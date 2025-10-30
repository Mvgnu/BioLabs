from .conftest import client, ensure_auth_headers
import uuid
from uuid import UUID
from datetime import datetime, timezone, timedelta


def get_auth_headers(client, email=None):
    headers, _ = ensure_auth_headers(client, email=email)
    return headers


def create_item(client, headers, item_type="sample", name="Item"):
    resp = client.post(
        "/api/inventory/items",
        json={"item_type": item_type, "name": name},
        headers=headers,
    )
    assert resp.status_code == 200
    return resp.json()


def test_analytics_summary(client):
    headers = get_auth_headers(client)
    baseline = client.get("/api/analytics/summary", headers=headers)
    assert baseline.status_code == 200
    baseline_counts = {d["item_type"]: d["count"] for d in baseline.json()}
    create_item(client, headers, "plasmid", "A")
    create_item(client, headers, "plasmid", "B")
    create_item(client, headers, "sample", "S1")

    resp = client.get("/api/analytics/summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    counts = {d["item_type"]: d["count"] for d in data}
    assert counts.get("plasmid", 0) - baseline_counts.get("plasmid", 0) == 2
    assert counts.get("sample", 0) - baseline_counts.get("sample", 0) == 1


def test_trending_protocols(client):
    headers = get_auth_headers(client)
    # create protocol template
    resp = client.post(
        "/api/protocols/templates",
        json={"name": "Test Proto", "content": "step"},
        headers=headers,
    )
    tpl_id = resp.json()["id"]
    # execute protocol multiple times
    for _ in range(3):
        client.post(
            "/api/protocols/executions",
            json={"template_id": tpl_id},
            headers=headers,
        )

    resp = client.get("/api/analytics/trending-protocols", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["template_id"] == tpl_id
    assert data[0]["count"] == 3


def test_trending_protocols_days_param(client):
    headers = get_auth_headers(client)
    resp = client.post(
        "/api/protocols/templates",
        json={"name": "Old Proto", "content": "step"},
        headers=headers,
    )
    tpl_id = resp.json()["id"]
    # create execution and set it 40 days in the past
    ex = client.post(
        "/api/protocols/executions",
        json={"template_id": tpl_id},
        headers=headers,
    ).json()
    from .conftest import TestingSessionLocal
    from app import models
    db = TestingSessionLocal()
    exec_obj = db.get(models.ProtocolExecution, UUID(ex["id"]))
    exec_obj.created_at = datetime.now(timezone.utc) - timedelta(days=40)
    db.commit()
    db.close()

    resp = client.get("/api/analytics/trending-protocols?days=30", headers=headers)
    assert all(r["template_id"] != tpl_id for r in resp.json())
    resp = client.get("/api/analytics/trending-protocols?days=60", headers=headers)
    assert any(r["template_id"] == tpl_id for r in resp.json())


def test_trending_protocols_recency_ranking(client):
    headers = get_auth_headers(client)
    t1 = client.post(
        "/api/protocols/templates",
        json={"name": "New", "content": "s"},
        headers=headers,
    ).json()["id"]
    t2 = client.post(
        "/api/protocols/templates",
        json={"name": "Old", "content": "s"},
        headers=headers,
    ).json()["id"]
    e1 = client.post(
        "/api/protocols/executions",
        json={"template_id": t1},
        headers=headers,
    ).json()
    e2 = client.post(
        "/api/protocols/executions",
        json={"template_id": t2},
        headers=headers,
    ).json()
    from .conftest import TestingSessionLocal
    from app import models
    db = TestingSessionLocal()
    exec2 = db.get(models.ProtocolExecution, UUID(e2["id"]))
    exec2.created_at = datetime.now(timezone.utc) - timedelta(days=5)
    db.commit()
    db.close()
    data = client.get("/api/analytics/trending-protocols", headers=headers).json()
    order = [r["template_id"] for r in data]
    assert order.index(t1) < order.index(t2)


def test_trending_articles(client):
    headers = get_auth_headers(client)
    resp = client.post(
        "/api/knowledge/articles",
        json={"title": "Tips", "content": "text"},
        headers=headers,
    )
    art_id = resp.json()["id"]
    for _ in range(4):
        client.get(f"/api/knowledge/articles/{art_id}", headers=headers)

    resp = client.get("/api/analytics/trending-articles", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["article_id"] == art_id
    assert data[0]["count"] == 4


def test_trending_articles_days_param(client):
    headers = get_auth_headers(client)
    resp = client.post(
        "/api/knowledge/articles",
        json={"title": "Old", "content": "t"},
        headers=headers,
    )
    art_id = resp.json()["id"]
    client.get(f"/api/knowledge/articles/{art_id}", headers=headers)
    from .conftest import TestingSessionLocal
    from app import models
    db = TestingSessionLocal()
    view = db.query(models.KnowledgeArticleView).filter_by(article_id=UUID(art_id)).first()
    view.viewed_at = datetime.now(timezone.utc) - timedelta(days=40)
    db.commit()
    db.close()
    resp = client.get("/api/analytics/trending-articles?days=30", headers=headers)
    assert all(r["article_id"] != art_id for r in resp.json())
    resp = client.get("/api/analytics/trending-articles?days=60", headers=headers)
    assert any(r["article_id"] == art_id for r in resp.json())


def test_trending_articles_recency_ranking(client):
    headers = get_auth_headers(client)
    a1 = client.post(
        "/api/knowledge/articles",
        json={"title": "Recent", "content": "t"},
        headers=headers,
    ).json()["id"]
    a2 = client.post(
        "/api/knowledge/articles",
        json={"title": "Old", "content": "t"},
        headers=headers,
    ).json()["id"]
    client.get(f"/api/knowledge/articles/{a1}", headers=headers)
    client.get(f"/api/knowledge/articles/{a2}", headers=headers)
    from .conftest import TestingSessionLocal
    from app import models
    db = TestingSessionLocal()
    view = db.query(models.KnowledgeArticleView).filter_by(article_id=UUID(a2)).first()
    view.viewed_at = datetime.now(timezone.utc) - timedelta(days=5)
    db.commit()
    db.close()
    data = client.get("/api/analytics/trending-articles", headers=headers).json()
    order = [r["article_id"] for r in data]
    assert order.index(a1) < order.index(a2)


def test_trending_items(client):
    headers = get_auth_headers(client)
    item1 = create_item(client, headers, name="A")
    item2 = create_item(client, headers, name="B")
    # create notebook entries referencing items
    for _ in range(3):
        client.post(
            "/api/notebook/entries",
            json={"title": "n", "content": "c", "item_id": item1["id"]},
            headers=headers,
        )
    for _ in range(2):
        client.post(
            "/api/notebook/entries",
            json={"title": "n", "content": "c", "item_id": item2["id"]},
            headers=headers,
        )

    resp = client.get("/api/analytics/trending-items", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["item_id"] == item1["id"]
    assert data[0]["count"] == 3


def test_trending_items_days_param(client):
    headers = get_auth_headers(client)
    item = create_item(client, headers, name="X")
    client.post(
        "/api/notebook/entries",
        json={"title": "n", "content": "c", "item_id": item["id"]},
        headers=headers,
    )
    from .conftest import TestingSessionLocal
    from app import models
    db = TestingSessionLocal()
    entry = db.query(models.NotebookEntry).filter_by(item_id=UUID(item["id"])).first()
    entry.created_at = datetime.now(timezone.utc) - timedelta(days=40)
    db.commit()
    db.close()
    resp = client.get("/api/analytics/trending-items?days=30", headers=headers)
    assert all(r["item_id"] != item["id"] for r in resp.json())
    resp = client.get("/api/analytics/trending-items?days=60", headers=headers)
    assert any(r["item_id"] == item["id"] for r in resp.json())


def test_trending_items_recency_ranking(client):
    headers = get_auth_headers(client)
    i1 = create_item(client, headers, name="recent")
    i2 = create_item(client, headers, name="old")
    client.post(
        "/api/notebook/entries",
        json={"title": "n", "content": "c", "item_id": i1["id"]},
        headers=headers,
    )
    e2 = client.post(
        "/api/notebook/entries",
        json={"title": "n", "content": "c", "item_id": i2["id"]},
        headers=headers,
    ).json()
    from .conftest import TestingSessionLocal
    from app import models
    db = TestingSessionLocal()
    entry = db.get(models.NotebookEntry, UUID(e2["id"]))
    entry.created_at = datetime.now(timezone.utc) - timedelta(days=5)
    db.commit()
    db.close()
    data = client.get("/api/analytics/trending-items", headers=headers).json()
    order = [r["item_id"] for r in data]
    assert order.index(i1["id"]) < order.index(i2["id"])


def test_trending_threads(client):
    headers = get_auth_headers(client)
    # create thread
    thread = client.post(
        "/api/forum/threads",
        json={"title": "Q1"},
        headers=headers,
    ).json()
    for _ in range(4):
        client.post(
            f"/api/forum/threads/{thread['id']}/posts",
            json={"content": "hi"},
            headers=headers,
        )

    resp = client.get("/api/analytics/trending-threads", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["thread_id"] == thread["id"]
    assert data[0]["count"] == 4


def test_trending_threads_days_param(client):
    headers = get_auth_headers(client)
    thread = client.post(
        "/api/forum/threads",
        json={"title": "Old"},
        headers=headers,
    ).json()
    client.post(
        f"/api/forum/threads/{thread['id']}/posts",
        json={"content": "msg"},
        headers=headers,
    )
    from .conftest import TestingSessionLocal
    from app import models
    db = TestingSessionLocal()
    post = db.query(models.ForumPost).filter_by(thread_id=UUID(thread["id"])).first()
    post.created_at = datetime.now(timezone.utc) - timedelta(days=40)
    db.commit()
    db.close()
    resp = client.get("/api/analytics/trending-threads?days=30", headers=headers)
    assert all(r["thread_id"] != thread["id"] for r in resp.json())
    resp = client.get("/api/analytics/trending-threads?days=60", headers=headers)
    assert any(r["thread_id"] == thread["id"] for r in resp.json())


def test_trending_posts(client):
    owner = get_auth_headers(client)
    viewer_one = get_auth_headers(client, email="viewer1@example.com")
    viewer_two = get_auth_headers(client, email="viewer2@example.com")

    asset = client.post(
        '/api/dna-assets',
        json={'name': 'Trending asset', 'sequence': 'ATGCATGC'},
        headers=owner,
    ).json()
    portfolio = client.post(
        '/api/community/portfolios',
        json={
            'slug': 'trending-portfolio',
            'title': 'Trending portfolio',
            'summary': 'Engagement stress test.',
            'assets': [{'asset_type': 'dna_asset', 'asset_id': asset['id']}],
        },
        headers=owner,
    ).json()
    client.post(
        f"/api/community/portfolios/{portfolio['id']}/moderation",
        json={'outcome': 'cleared'},
        headers=owner,
    )
    client.post(
        f"/api/community/portfolios/{portfolio['id']}/engagements",
        json={'interaction': 'star'},
        headers=viewer_one,
    )
    client.post(
        f"/api/community/portfolios/{portfolio['id']}/engagements",
        json={'interaction': 'bookmark'},
        headers=viewer_two,
    )
    data = client.get("/api/analytics/trending-posts", headers=owner).json()
    assert data[0]['portfolio_id'] == portfolio['id']
    assert data[0]['engagement_count'] >= 1.5


def test_trending_protocol_stars(client):
    h1 = get_auth_headers(client)
    h2 = get_auth_headers(client, email="p2@example.com")
    tpl1 = client.post(
        "/api/protocols/templates",
        json={"name": "S1", "content": "s"},
        headers=h1,
    ).json()
    tpl2 = client.post(
        "/api/protocols/templates",
        json={"name": "S2", "content": "s"},
        headers=h1,
    ).json()
    client.post(f"/api/protocols/templates/{tpl1['id']}/star", headers=h1)
    client.post(f"/api/protocols/templates/{tpl1['id']}/star", headers=h2)
    client.post(f"/api/protocols/templates/{tpl2['id']}/star", headers=h1)
    data = client.get("/api/analytics/trending-protocol-stars", headers=h1).json()
    assert data[0]["template_id"] == tpl1["id"]
    assert data[0]["count"] == 2


def test_trending_article_stars(client):
    h1 = get_auth_headers(client)
    h2 = get_auth_headers(client, email=f"u{uuid.uuid4()}@example.com")
    art1 = client.post(
        "/api/knowledge/articles",
        json={"title": "A1", "content": "c"},
        headers=h1,
    ).json()["id"]
    art2 = client.post(
        "/api/knowledge/articles",
        json={"title": "A2", "content": "c"},
        headers=h1,
    ).json()["id"]
    client.post(f"/api/knowledge/articles/{art1}/star", headers=h1)
    client.post(f"/api/knowledge/articles/{art1}/star", headers=h2)
    client.post(f"/api/knowledge/articles/{art2}/star", headers=h1)
    data = client.get("/api/analytics/trending-article-stars", headers=h1).json()
    assert data[0]["article_id"] == art1
    assert data[0]["count"] == 2


def test_trending_article_comments(client):
    h = get_auth_headers(client)
    art = (
        client.post(
            "/api/knowledge/articles",
            json={"title": "C1", "content": "c"},
            headers=h,
        ).json()["id"]
    )
    for _ in range(3):
        client.post(
            "/api/comments",
            json={"content": "hi", "knowledge_article_id": art},
            headers=h,
        )
    data = client.get("/api/analytics/trending-article-comments", headers=h).json()
    assert data[0]["article_id"] == art
    assert data[0]["count"] == 3
