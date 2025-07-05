import uuid
from .conftest import client


def get_headers(client):
    resp = client.post(
        "/api/auth/register", json={"email": f"{uuid.uuid4()}@ex.com", "password": "secret"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_tool_run(client):
    headers = get_headers(client)
    code = "def run(item):\n    return {'name': item['name']}"
    tool = client.post(
        "/api/tools",
        json={"name": "Echo", "code": code},
        headers=headers,
    )
    assert tool.status_code == 200
    tool_id = tool.json()["id"]

    item = client.post(
        "/api/inventory/items",
        json={"item_type": "sample", "name": "ToolItem"},
        headers=headers,
    ).json()

    run_resp = client.post(
        f"/api/tools/{tool_id}/run",
        json={"item_id": item["id"]},
        headers=headers,
    )
    assert run_resp.status_code == 200
    assert run_resp.json()["result"]["name"] == "ToolItem"
