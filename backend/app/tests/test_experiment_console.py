from datetime import datetime, timezone, timedelta
import uuid

from .conftest import TestingSessionLocal
from app import models
from app.auth import create_access_token


def get_headers(client):
    email = f"{uuid.uuid4()}@example.com"
    token = create_access_token({"sub": email})
    db = TestingSessionLocal()
    try:
        user = models.User(email=email, hashed_password="placeholder")
        db.add(user)
        db.commit()
    finally:
        db.close()
    return {"Authorization": f"Bearer {token}"}


def test_create_and_update_execution_session(client):
    headers = get_headers(client)

    template = client.post(
        "/api/protocols/templates",
        json={"name": "Console Protocol", "content": "Prep\nExecute"},
        headers=headers,
    ).json()

    inventory = client.post(
        "/api/inventory/items",
        json={"item_type": "sample", "name": "Buffer"},
        headers=headers,
    ).json()

    resource = client.post(
        "/api/schedule/resources",
        json={"name": "Centrifuge"},
        headers=headers,
    ).json()

    now = datetime.now(timezone.utc)
    booking = client.post(
        "/api/schedule/bookings",
        json={
            "resource_id": resource["id"],
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(minutes=30)).isoformat(),
        },
        headers=headers,
    ).json()

    created = client.post(
        "/api/experiment-console/sessions",
        json={
            "template_id": template["id"],
            "title": "Console Run",
            "inventory_item_ids": [inventory["id"]],
            "booking_ids": [booking["id"]],
        },
        headers=headers,
    )

    assert created.status_code == 200
    session_payload = created.json()
    assert session_payload["execution"]["status"] == "in_progress"
    assert session_payload["protocol"]["id"] == template["id"]
    assert session_payload["inventory_items"][0]["id"] == inventory["id"]
    assert session_payload["bookings"][0]["id"] == booking["id"]
    assert len(session_payload["steps"]) == 2
    assert session_payload["steps"][0]["status"] == "pending"
    assert session_payload["notebook_entries"]

    exec_id = session_payload["execution"]["id"]

    fetched = client.get(
        f"/api/experiment-console/sessions/{exec_id}", headers=headers
    )
    assert fetched.status_code == 200
    assert fetched.json()["execution"]["id"] == exec_id

    update_resp = client.post(
        f"/api/experiment-console/sessions/{exec_id}/steps/0",
        json={
            "status": "completed",
            "started_at": now.isoformat(),
            "completed_at": now.isoformat(),
        },
        headers=headers,
    )
    assert update_resp.status_code == 200
    updated = update_resp.json()
    assert updated["steps"][0]["status"] == "completed"
    assert updated["execution"]["status"] in {"in_progress", "completed"}


def test_step_gating_blocks_progress(client):
    headers = get_headers(client)

    template = client.post(
        "/api/protocols/templates",
        json={"name": "Gated Protocol", "content": "Stage 1\nStage 2"},
        headers=headers,
    ).json()

    inventory = client.post(
        "/api/inventory/items",
        json={"item_type": "reagent", "name": "Buffer A"},
        headers=headers,
    ).json()

    client.put(
        f"/api/inventory/items/{inventory['id']}",
        json={"status": "consumed"},
        headers=headers,
    )

    now = datetime.now(timezone.utc)

    created = client.post(
        "/api/experiment-console/sessions",
        json={
            "template_id": template["id"],
            "inventory_item_ids": [inventory["id"]],
            "booking_ids": [],
        },
        headers=headers,
    )

    assert created.status_code == 200
    session_payload = created.json()
    step_state = session_payload["steps"][0]
    assert step_state["blocked_reason"]
    assert any(action.startswith("inventory:restore") for action in step_state["required_actions"])

    exec_id = session_payload["execution"]["id"]

    forced_update = client.post(
        f"/api/experiment-console/sessions/{exec_id}/steps/0",
        json={"status": "in_progress", "started_at": now.isoformat()},
        headers=headers,
    )
    assert forced_update.status_code == 409
    blocked_detail = forced_update.json()["detail"]
    assert blocked_detail["blocked_reason"]

    advance_attempt = client.post(
        f"/api/experiment-console/sessions/{exec_id}/steps/0/advance",
        headers=headers,
    )
    assert advance_attempt.status_code == 409
    advance_detail = advance_attempt.json()["detail"]
    assert advance_detail["blocked_reason"]

    client.put(
        f"/api/inventory/items/{inventory['id']}",
        json={"status": "available"},
        headers=headers,
    )

    advance_success = client.post(
        f"/api/experiment-console/sessions/{exec_id}/steps/0/advance",
        headers=headers,
    )
    assert advance_success.status_code == 200
    after_payload = advance_success.json()
    assert after_payload["steps"][0]["status"] == "in_progress"
    assert after_payload["steps"][0]["blocked_reason"] is None


def test_step_remediation_auto_executes_inventory(client):
    headers = get_headers(client)

    template = client.post(
        "/api/protocols/templates",
        json={"name": "Remediation Protocol", "content": "Prep"},
        headers=headers,
    ).json()

    inventory = client.post(
        "/api/inventory/items",
        json={"item_type": "reagent", "name": "Buffer B"},
        headers=headers,
    ).json()

    client.put(
        f"/api/inventory/items/{inventory['id']}",
        json={"status": "consumed"},
        headers=headers,
    )

    created = client.post(
        "/api/experiment-console/sessions",
        json={
            "template_id": template["id"],
            "inventory_item_ids": [inventory["id"]],
            "booking_ids": [],
        },
        headers=headers,
    )
    assert created.status_code == 200
    exec_id = created.json()["execution"]["id"]

    remediation = client.post(
        f"/api/experiment-console/sessions/{exec_id}/steps/0/remediate",
        json={"auto": True},
        headers=headers,
    )

    assert remediation.status_code == 200
    payload = remediation.json()
    assert payload["results"]
    assert any(result["status"] == "executed" for result in payload["results"])
    session = payload["session"]
    assert session["steps"][0]["blocked_reason"] is None

    db = TestingSessionLocal()
    try:
        refreshed_item = (
            db.query(models.InventoryItem)
            .filter(models.InventoryItem.id == uuid.UUID(inventory["id"]))
            .first()
        )
        assert refreshed_item is not None
        assert refreshed_item.status == "reserved"
    finally:
        db.close()
