from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app import models, notify
from app.auth import create_access_token
from app.services import sample_governance as governance_service
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

    db = TestingSessionLocal()
    try:
        template = models.ProtocolTemplate(
            name="Sample Protocol",
            version="1.0",
            content="steps",
            team_id=team_id,
            created_by=admin_id,
        )
        db.add(template)
        db.flush()
        execution = models.ProtocolExecution(
            template_id=template.id,
            run_by=admin_id,
            status="running",
        )
        db.add(execution)
        db.flush()
        event = models.ExecutionEvent(
            execution_id=execution.id,
            event_type="protocol.step.completed",
            payload={"step": "incubate"},
            sequence=1,
        )
        db.add(event)
        db.commit()
        execution_id = execution.id
        event_id = event.id
    finally:
        db.close()

    payload = {
        "asset_version_id": None,
        "planner_session_id": None,
        "performed_for_team_id": str(team_id),
        "compartment_id": str(compartment_id),
        "custody_action": "deposit",
        "quantity": 3,
        "quantity_units": "vials",
        "meta": {"guardrail_flags": ["fault.temperature.high"]},
        "protocol_execution_id": str(execution_id),
        "execution_event_id": str(event_id),
    }

    response = client.post(
        "/api/governance/custody/logs",
        json=payload,
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert "capacity.exceeded" in body["guardrail_flags"]
    assert body["protocol_execution_id"] == str(execution_id)
    assert body["execution_event_id"] == str(event_id)

    escalations = client.get("/api/governance/custody/escalations", headers=headers)
    assert escalations.status_code == 200
    escalation_payload = escalations.json()
    assert len(escalation_payload) == 1
    escalation_id = escalation_payload[0]["id"]
    assert escalation_payload[0]["severity"] == "critical"
    assert escalation_payload[0]["status"] == "open"
    assert escalation_payload[0]["protocol_execution_id"] == str(execution_id)
    assert escalation_payload[0]["execution_event_id"] == str(event_id)
    context = escalation_payload[0]["protocol_execution"]
    assert context and context["id"] == str(execution_id)

    protocols = client.get(
        "/api/governance/custody/protocols",
        headers=headers,
    )
    assert protocols.status_code == 200
    protocol_rows = protocols.json()
    assert len(protocol_rows) == 1
    snapshot = protocol_rows[0]
    assert snapshot["guardrail_status"] == "halted"
    assert snapshot["open_escalations"] == 1
    overlays = snapshot["event_overlays"]
    assert str(event_id) in overlays
    overlay = overlays[str(event_id)]
    assert str(escalation_id) in overlay["escalation_ids"]
    assert overlay["mitigation_checklist"], "expected mitigation checklist entries"

    drill_session = TestingSessionLocal()
    try:
        escalation_row = drill_session.get(
            models.GovernanceCustodyEscalation, uuid.UUID(escalation_id)
        )
        assert escalation_row is not None
        drill_meta = dict(escalation_row.meta or {})
        drill_meta["recovery_drill_open"] = True
        escalation_row.meta = drill_meta
        escalation_row.updated_at = datetime.now(timezone.utc)
        drill_session.add(escalation_row)
        drill_session.commit()
        governance_service._sync_protocol_escalation_state(
            drill_session, escalation_row
        )
        drill_session.commit()
    finally:
        drill_session.close()

    drill_filtered = client.get(
        "/api/governance/custody/protocols",
        params={"has_open_drill": True},
        headers=headers,
    )
    assert drill_filtered.status_code == 200
    assert drill_filtered.json()[0]["open_drill_count"] >= 1

    critical_filtered = client.get(
        "/api/governance/custody/protocols",
        params={"severity": "critical"},
        headers=headers,
    )
    assert critical_filtered.status_code == 200
    assert critical_filtered.json()[0]["guardrail_status"] == "halted"

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

    db_check = TestingSessionLocal()
    try:
        execution_row = db_check.get(models.ProtocolExecution, execution_id)
        assert execution_row is not None
        custody_state = (execution_row.result or {}).get("custody", {})
        ledger = custody_state.get("ledger", [])
        assert any(entry["log_id"] == body["id"] for entry in ledger)
        escalation_state = custody_state.get("escalations", {})
        assert escalation_state[str(escalation_id)]["status"] == "resolved"
    finally:
        db_check.close()

    post_resolution = client.get(
        "/api/governance/custody/protocols",
        headers=headers,
    )
    assert post_resolution.status_code == 200
    resolved_snapshot = post_resolution.json()[0]
    assert resolved_snapshot["open_escalations"] == 0
    assert resolved_snapshot["guardrail_status"] in {"stabilizing", "stable"}

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
