from __future__ import annotations

import uuid

from app import models, notify
from app.auth import create_access_token
from app.tests.conftest import TestingSessionLocal


def _admin_headers() -> tuple[dict[str, str], uuid.UUID]:
    email = f"custody-admin-{uuid.uuid4()}@example.com"
    token = create_access_token({"sub": email})
    db = TestingSessionLocal()
    try:
        user = models.User(email=email, hashed_password="placeholder", is_admin=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"Authorization": f"Bearer {token}"}, user.id
    finally:
        db.close()


def _bootstrap_custody_fixture(admin_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    db = TestingSessionLocal()
    try:
        team = models.Team(name="Governance Ops", created_by=admin_id)
        db.add(team)
        db.flush()

        freezer = models.GovernanceFreezerUnit(
            name="-80C Freezer",
            status="active",
            team_id=team.id,
            guardrail_config={"escalation": {"critical_sla_minutes": 5}},
        )
        db.add(freezer)
        db.flush()

        compartment = models.GovernanceFreezerCompartment(
            freezer_id=freezer.id,
            label="Rack A",
            position_index=0,
            capacity=1,
            guardrail_thresholds={"max_capacity": 1, "escalation": {"warning_sla_minutes": 30}},
        )
        db.add(compartment)

        member = models.TeamMember(team_id=team.id, user_id=admin_id, role="governance_lead")
        db.add(member)

        db.commit()
        return team.id, freezer.id, compartment.id
    finally:
        db.close()


def _user_headers() -> dict[str, str]:
    email = f"custody-user-{uuid.uuid4()}@example.com"
    token = create_access_token({"sub": email})
    db = TestingSessionLocal()
    try:
        user = models.User(email=email, hashed_password="placeholder", is_admin=False)
        db.add(user)
        db.commit()
        return {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


def test_custody_routes_enforce_admin_rbac(client):
    headers = _user_headers()
    response = client.get("/api/governance/custody/freezers", headers=headers)
    assert response.status_code == 403


def test_custody_escalation_and_fault_flow(client):
    notify.EMAIL_OUTBOX.clear()
    headers, admin_id = _admin_headers()
    team_id, freezer_id, compartment_id = _bootstrap_custody_fixture(admin_id)

    payload = {
        "asset_version_id": None,
        "planner_session_id": None,
        "performed_for_team_id": str(team_id),
        "compartment_id": str(compartment_id),
        "custody_action": "deposit",
        "quantity": 3,
        "quantity_units": "vials",
        "meta": {"guardrail_flags": ["fault.temperature.high"]},
    }

    response = client.post(
        "/api/governance/custody/logs",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert "capacity.exceeded" in body["guardrail_flags"]

    escalations = client.get("/api/governance/custody/escalations", headers=headers)
    assert escalations.status_code == 200
    escalation_payload = escalations.json()
    assert len(escalation_payload) == 1
    escalation_id = escalation_payload[0]["id"]
    assert escalation_payload[0]["severity"] == "critical"
    assert escalation_payload[0]["status"] == "open"

    # Notifications are issued automatically on escalation creation
    assert any("Custody escalation" in subject for _, subject, _ in notify.EMAIL_OUTBOX)

    ack = client.post(
        f"/api/governance/custody/escalations/{escalation_id}/acknowledge",
        headers=headers,
    )
    assert ack.status_code == 200
    ack_payload = ack.json()
    assert ack_payload["status"] == "acknowledged"

    resolved = client.post(
        f"/api/governance/custody/escalations/{escalation_id}/resolve",
        headers=headers,
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"

    faults = client.get("/api/governance/custody/faults", headers=headers)
    assert faults.status_code == 200
    fault_payload = faults.json()
    assert len(fault_payload) == 1
    fault_id = fault_payload[0]["id"]
    assert fault_payload[0]["guardrail_flag"] == "fault.temperature.high"

    resolve_fault = client.post(
        f"/api/governance/custody/faults/{fault_id}/resolve",
        headers=headers,
    )
    assert resolve_fault.status_code == 200
    assert resolve_fault.json()["resolved_at"] is not None

    # Posting a balancing log without guardrails should leave escalation queue empty
    clear_payload = {
        "performed_for_team_id": str(team_id),
        "compartment_id": str(compartment_id),
        "custody_action": "removed",
        "quantity": 3,
        "quantity_units": "vials",
    }
    clear_response = client.post(
        "/api/governance/custody/logs",
        json=clear_payload,
        headers=headers,
    )
    assert clear_response.status_code == 201
    queue = client.get("/api/governance/custody/escalations", headers=headers)
    assert queue.status_code == 200
    assert queue.json()[0]["status"] == "resolved"
