import json
import uuid
from .conftest import client


def get_headers(client, email="ws@example.com"):
    resp = client.post("/api/auth/register", json={"email": email, "password": "secret"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


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
