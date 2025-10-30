import json
import uuid
from .conftest import client, ensure_auth_headers


def get_headers(client, email="ws@example.com"):
    headers, _ = ensure_auth_headers(client, email=email)
    return headers


def test_websocket_receives_item_events(client):
    headers = get_headers(client)
    team_resp = client.post("/api/teams/", json={"name": "WSTeam"}, headers=headers)
    team_id = team_resp.json()["id"]

    with client.websocket_connect(f"/ws/{team_id}") as websocket:
        item_resp = client.post(
            "/api/inventory/items",
            json={"item_type": "sample", "name": "WSItem", "team_id": team_id},
            headers=headers,
        )
        data = websocket.receive_text()
        msg = json.loads(data)
        assert msg["type"] == "item_created"
        assert msg["id"] == item_resp.json()["id"]
