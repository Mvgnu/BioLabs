from .conftest import client
import uuid


def auth_header(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": f"{uuid.uuid4()}@ex.com", "password": "pw"},
    )
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_assistant_reply(client):
    headers = auth_header(client)
    # create a project to mention
    project = client.post(
        "/api/projects",
        json={"name": "TestProject"},
        headers=headers,
    ).json()

    res = client.post(
        "/api/assistant/ask",
        json={"question": "What projects are active?"},
        headers=headers,
    )
    assert res.status_code == 200
    assert "TestProject" in res.json()["message"]

    hist = client.get("/api/assistant", headers=headers)
    assert hist.status_code == 200
    assert len(hist.json()) == 2


def test_inventory_forecast(client):
    headers = auth_header(client)
    item = client.post(
        "/api/inventory/items",
        json={"item_type": "sample", "name": "Reagent", "custom_data": {"stock": 10}},
        headers=headers,
    ).json()
    for _ in range(5):
        client.post(
            "/api/notebook/entries",
            json={"title": "Use", "content": "c", "item_id": item["id"]},
            headers=headers,
        )
    resp = client.get("/api/assistant/forecast", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data and data[0]["item_id"] == item["id"]


def test_protocol_suggestion(client):
    headers = auth_header(client)
    tpl = client.post(
        "/api/protocols/templates",
        json={"name": "PCR", "content": "Use enzyme", "variables": ["enzyme"]},
        headers=headers,
    ).json()
    itm = client.post(
        "/api/inventory/items",
        json={"item_type": "enzyme", "name": "Taq enzyme"},
        headers=headers,
    ).json()
    resp = client.get("/api/assistant/suggest", params={"goal": "PCR"}, headers=headers)
    assert resp.status_code == 200
    sugg = resp.json()
    assert sugg and sugg[0]["protocol_id"] == tpl["id"]
    assert sugg[0]["materials"] and sugg[0]["materials"][0]["id"] == itm["id"]


def test_experiment_design(client):
    headers = auth_header(client)
    client.post(
        "/api/knowledge/articles",
        json={"title": "Blot tips", "content": "Use PVDF", "tags": ["blot"]},
        headers=headers,
    )
    tpl = client.post(
        "/api/protocols/templates",
        json={"name": "Western blot", "content": "Run gel", "variables": ["buffer"]},
        headers=headers,
    ).json()
    itm = client.post(
        "/api/inventory/items",
        json={"item_type": "buffer", "name": "Transfer buffer"},
        headers=headers,
    ).json()

    resp = client.get("/api/assistant/design", params={"goal": "blot"}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["protocol"]["protocol_id"] == tpl["id"]
    assert data["protocol"]["materials"][0]["id"] == itm["id"]
    assert data["articles"]


