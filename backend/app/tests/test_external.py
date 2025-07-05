import uuid
from .conftest import client


def auth_headers(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": f"{uuid.uuid4()}@ex.com", "password": "secret"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_pubmed_search(monkeypatch, client):
    headers = auth_headers(client)

    def fake_search(query, limit=5):
        return [
            {"id": "1", "title": "Article A"},
            {"id": "2", "title": "Article B"},
        ]

    monkeypatch.setattr("app.routes.external.search_pubmed", fake_search)
    resp = client.post(
        "/api/external/pubmed",
        json={"query": "cancer", "limit": 2},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["title"] == "Article A"
