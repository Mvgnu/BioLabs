import uuid
from .conftest import client


def get_headers(client):
    resp = client.post(
        "/api/auth/register",
        json={"email": f"{uuid.uuid4()}@ex.com", "password": "secret"},
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_workflow_run(client):
    headers = get_headers(client)
    code = "def run(item):\n    return {'name': item['name']}"
    tool = client.post("/api/tools", json={"name": "Echo", "code": code}, headers=headers).json()
    wf = client.post(
        "/api/workflows",
        json={"name": "WF", "steps": [{"type": "tool", "id": tool['id']}]},
        headers=headers,
    ).json()
    item = client.post(
        "/api/inventory/items",
        json={"item_type": "sample", "name": "Item1"},
        headers=headers,
    ).json()
    exec_resp = client.post(
        "/api/workflows/run",
        json={"workflow_id": wf['id'], "item_id": item['id']},
        headers=headers,
    )
    assert exec_resp.status_code == 200
    data = exec_resp.json()
    assert data["status"] == "completed"
    assert data["result"][0]["name"] == "Item1"


def test_workflow_condition(client):
    headers = get_headers(client)
    code = "def run(item):\n    return {'val': 1}"
    tool = client.post("/api/tools", json={"name": "Tool", "code": code}, headers=headers).json()
    wf = client.post(
        "/api/workflows",
        json={
            "name": "WF2",
            "steps": [
                {"type": "tool", "id": tool["id"]},
                {"type": "tool", "id": tool["id"], "condition": "results[0]['val'] > 0"},
            ],
        },
        headers=headers,
    ).json()
    item = client.post(
        "/api/inventory/items",
        json={"item_type": "sample", "name": "X"},
        headers=headers,
    ).json()
    resp = client.post(
        "/api/workflows/run",
        json={"workflow_id": wf["id"], "item_id": item["id"]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()["result"]) == 2
