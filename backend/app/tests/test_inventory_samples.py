import uuid
from datetime import datetime, timezone

from app import models
from app.auth import create_access_token
from app.tests.conftest import TestingSessionLocal


def _admin_headers() -> tuple[dict[str, str], uuid.UUID]:
    email = f"samples-admin-{uuid.uuid4()}@example.com"
    token = create_access_token({"sub": email})
    db = TestingSessionLocal()
    try:
        user = models.User(email=email, hashed_password="placeholder", is_admin=True)
        db.add(user)
        db.flush()
        team = models.Team(name="Sample Ops", created_by=user.id)
        db.add(team)
        db.flush()
        membership = models.TeamMember(team_id=team.id, user_id=user.id, role="owner")
        db.add(membership)
        db.commit()
        return {"Authorization": f"Bearer {token}"}, team.id
    finally:
        db.close()


def test_sample_custody_summary_and_detail(client):
    headers, team_id = _admin_headers()
    item_resp = client.post(
        "/api/inventory/items",
        json={
            "item_type": "sample",
            "name": "Operable Sample",
            "team_id": str(team_id),
        },
        headers=headers,
    )
    assert item_resp.status_code == 200
    item = item_resp.json()

    log_resp = client.post(
        "/api/governance/custody/logs",
        json={
            "inventory_item_id": item["id"],
            "custody_action": "withdrawn",
            "performed_for_team_id": str(team_id),
            "performed_at": datetime.now(timezone.utc).isoformat(),
        },
        headers=headers,
    )
    assert log_resp.status_code == 201
    log = log_resp.json()
    assert log["inventory_item_id"] == item["id"]

    summaries_resp = client.get("/api/inventory/samples", headers=headers)
    assert summaries_resp.status_code == 200
    summaries = summaries_resp.json()
    assert any(summary["id"] == item["id"] for summary in summaries)
    summary = next(summary for summary in summaries if summary["id"] == item["id"])
    assert summary["custody_state"] == "in_transit"
    assert summary["open_escalations"] == 0
    assert summary["custody_snapshot"]["last_action"] == "withdrawn"

    detail_resp = client.get(
        f"/api/inventory/items/{item['id']}/custody",
        headers=headers,
    )
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["item"]["id"] == item["id"]
    assert detail["recent_logs"][0]["id"] == log["id"]
    assert detail["recent_logs"][0]["inventory_item_id"] == item["id"]
    assert detail["escalations"] == []
