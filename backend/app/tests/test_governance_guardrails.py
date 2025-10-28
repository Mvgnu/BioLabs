from datetime import datetime, timedelta, timezone
import uuid

from app import models
from app.auth import create_access_token
from app.services import approval_ladders
from .conftest import TestingSessionLocal


def create_headers(is_admin: bool = False):
    email = f"guardrail+{uuid.uuid4()}@example.com"
    token = create_access_token({"sub": email})
    db = TestingSessionLocal()
    try:
        user = models.User(email=email, hashed_password="placeholder", is_admin=is_admin)
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = str(user.id)
    finally:
        db.close()
    return {"Authorization": f"Bearer {token}"}, user_id


def test_guardrail_simulation_flow(client):
    headers, user_id = create_headers()

    template = client.post(
        "/api/protocols/templates",
        json={"name": "Guardrail Template", "content": "Prep"},
        headers=headers,
    ).json()

    session = client.post(
        "/api/experiment-console/sessions",
        json={"template_id": template["id"], "title": "Guardrail Run"},
        headers=headers,
    ).json()

    execution_id = session["execution"]["id"]

    now = datetime.now(timezone.utc)
    request_payload = {
        "execution_id": execution_id,
        "metadata": {"scenario": "delegate reversal"},
        "comparisons": [
            {
                "index": 1,
                "name": "QA Review",
                "required_role": "qa",
                "mapped_step_indexes": [0],
                "gate_keys": ["qa"],
                "baseline": {
                    "status": "ready",
                    "sla_hours": 4,
                    "projected_due_at": (now + timedelta(hours=2)).isoformat(),
                    "blockers": [],
                    "required_actions": [],
                    "auto_triggers": [],
                    "assignee_id": user_id,
                    "delegate_id": None,
                },
                "simulated": {
                    "status": "pending",
                    "sla_hours": 6,
                    "projected_due_at": (now + timedelta(hours=5)).isoformat(),
                    "blockers": ["missing-signoff"],
                    "required_actions": ["notify:qa"],
                    "auto_triggers": [],
                    "assignee_id": user_id,
                    "delegate_id": None,
                },
            }
        ],
    }

    response = client.post(
        "/api/governance/guardrails/simulations",
        json=request_payload,
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["summary"]["state"] == "blocked"
    assert payload["metadata"]["scenario"] == "delegate reversal"
    assert payload["projected_delay_minutes"] >= 60

    record_id = payload["id"]

    listing = client.get(
        f"/api/governance/guardrails/simulations?execution_id={execution_id}",
        headers=headers,
    )
    assert listing.status_code == 200, listing.text
    simulations = listing.json()
    assert len(simulations) >= 1
    assert simulations[0]["id"] == record_id

    fetched = client.get(
        f"/api/governance/guardrails/simulations/{record_id}",
        headers=headers,
    )
    assert fetched.status_code == 200
    assert fetched.json()["summary"]["reasons"]

    other_headers, _ = create_headers()
    forbidden = client.get(
        f"/api/governance/guardrails/simulations?execution_id={execution_id}",
        headers=other_headers,
    )
    assert forbidden.status_code == 403

    db = TestingSessionLocal()
    try:
        stored = (
            db.query(models.GovernanceGuardrailSimulation)
            .filter(models.GovernanceGuardrailSimulation.id == uuid.UUID(record_id))
            .first()
        )
        assert stored is not None
        assert stored.state == "blocked"
        assert stored.summary["reasons"]
    finally:
        db.close()


def test_export_history_includes_guardrail_forecast(client):
    headers, user_id = create_headers()

    template = client.post(
        "/api/protocols/templates",
        json={"name": "Guardrail Template", "content": "Prep"},
        headers=headers,
    ).json()

    session = client.post(
        "/api/experiment-console/sessions",
        json={"template_id": template["id"], "title": "Guardrail Run"},
        headers=headers,
    ).json()

    execution_id = session["execution"]["id"]

    create_export = client.post(
        f"/api/experiment-console/sessions/{execution_id}/exports/narrative",
        json={"notes": "Forecast binding"},
        headers=headers,
    )
    assert create_export.status_code == 200, create_export.text

    now = datetime.now(timezone.utc)
    guardrail_payload = {
        "execution_id": execution_id,
        "metadata": {"scenario": "blocked"},
        "comparisons": [
            {
                "index": 1,
                "name": "QA Review",
                "required_role": "qa",
                "mapped_step_indexes": [0],
                "gate_keys": ["qa"],
                "baseline": {
                    "status": "ready",
                    "sla_hours": 2,
                    "projected_due_at": (now + timedelta(hours=1)).isoformat(),
                    "blockers": [],
                    "required_actions": [],
                    "auto_triggers": [],
                    "assignee_id": user_id,
                    "delegate_id": None,
                },
                "simulated": {
                    "status": "pending",
                    "sla_hours": 6,
                    "projected_due_at": (now + timedelta(hours=5)).isoformat(),
                    "blockers": ["missing-signoff"],
                    "required_actions": ["notify:qa"],
                    "auto_triggers": [],
                    "assignee_id": user_id,
                    "delegate_id": None,
                },
            }
        ],
    }

    forecast_response = client.post(
        "/api/governance/guardrails/simulations",
        json=guardrail_payload,
        headers=headers,
    )
    assert forecast_response.status_code == 200, forecast_response.text

    history = client.get(
        f"/api/experiment-console/sessions/{execution_id}/exports/narrative",
        headers=headers,
    )
    assert history.status_code == 200, history.text
    exports = history.json()["exports"]
    assert exports, "Expected export history payload"
    guardrail = exports[0].get("guardrail_simulation")
    assert guardrail is not None


def test_guardrail_health_reports_sanitized_queue_state(client):
    headers, user_id = create_headers(is_admin=True)

    template = client.post(
        "/api/protocols/templates",
        json={"name": "Guardrail Template", "content": "Prep"},
        headers=headers,
    ).json()

    session_resp = client.post(
        "/api/experiment-console/sessions",
        json={"template_id": template["id"], "title": "Guardrail Health"},
        headers=headers,
    )
    assert session_resp.status_code == 200, session_resp.text
    execution_id = session_resp.json()["execution"]["id"]

    export_resp = client.post(
        f"/api/experiment-console/sessions/{execution_id}/exports/narrative",
        json={"notes": "Health snapshot"},
        headers=headers,
    )
    assert export_resp.status_code == 200, export_resp.text
    export_payload = export_resp.json()
    export_id = export_payload["id"]

    now = datetime.now(timezone.utc)
    simulation_payload = {
        "execution_id": execution_id,
        "metadata": {"scenario": "blocked"},
        "comparisons": [
            {
                "index": 1,
                "name": "QA Review",
                "required_role": "qa",
                "mapped_step_indexes": [0],
                "gate_keys": ["qa"],
                "baseline": {
                    "status": "ready",
                    "sla_hours": 2,
                    "projected_due_at": (now + timedelta(hours=1)).isoformat(),
                    "blockers": [],
                    "required_actions": [],
                    "auto_triggers": [],
                    "assignee_id": user_id,
                    "delegate_id": None,
                },
                "simulated": {
                    "status": "pending",
                    "sla_hours": 6,
                    "projected_due_at": (now + timedelta(hours=5)).isoformat(),
                    "blockers": ["missing-signoff"],
                    "required_actions": ["notify:qa"],
                    "auto_triggers": [],
                    "assignee_id": user_id,
                    "delegate_id": None,
                },
            }
        ],
    }

    sim_resp = client.post(
        "/api/governance/guardrails/simulations",
        json=simulation_payload,
        headers=headers,
    )
    assert sim_resp.status_code == 200, sim_resp.text

    session = TestingSessionLocal()
    try:
        export_record = session.get(models.ExecutionNarrativeExport, uuid.UUID(export_id))
        assert export_record is not None
        approval_ladders.record_packaging_queue_state(
            session, export=export_record, actor=None
        )
        session.commit()
    finally:
        session.close()

    health_resp = client.get(
        "/api/governance/guardrails/health",
        headers=headers,
    )
    assert health_resp.status_code == 200, health_resp.text
    report = health_resp.json()

    totals = report["totals"]
    assert totals["total_exports"] >= 1
    breakdown = report["state_breakdown"]
    assert "guardrail_blocked" in breakdown or "awaiting_approval" in breakdown

    entries = report["queue"]
    target = next((entry for entry in entries if entry["export_id"] == export_id), None)
    assert target is not None
    assert target["approval_status"]
    assert target["artifact_status"]
    if target["context"]:
        allowed_keys = {
            "guardrail_state",
            "projected_delay_minutes",
            "reasons",
            "pending_stage_id",
            "pending_stage_index",
            "pending_stage_status",
            "pending_stage_due_at",
        }
        assert set(target["context"].keys()).issubset(allowed_keys)


def test_guardrail_simulation_clear_for_multi_stage(client):
    headers, user_id = create_headers()

    template = client.post(
        "/api/protocols/templates",
        json={"name": "Guardrail Template", "content": "Prep"},
        headers=headers,
    ).json()

    session = client.post(
        "/api/experiment-console/sessions",
        json={"template_id": template["id"], "title": "Guardrail Run"},
        headers=headers,
    ).json()

    execution_id = session["execution"]["id"]

    now = datetime.now(timezone.utc)
    request_payload = {
        "execution_id": execution_id,
        "metadata": {"scenario": "optimized assignment"},
        "comparisons": [
            {
                "index": 1,
                "name": "Primary QA",
                "required_role": "qa",
                "mapped_step_indexes": [0],
                "gate_keys": ["qa"],
                "baseline": {
                    "status": "ready",
                    "sla_hours": 4,
                    "projected_due_at": (now + timedelta(hours=2)).isoformat(),
                    "blockers": [],
                    "required_actions": [],
                    "auto_triggers": [],
                    "assignee_id": user_id,
                    "delegate_id": None,
                },
                "simulated": {
                    "status": "ready",
                    "sla_hours": 4,
                    "projected_due_at": (now + timedelta(hours=2)).isoformat(),
                    "blockers": [],
                    "required_actions": [],
                    "auto_triggers": [],
                    "assignee_id": user_id,
                    "delegate_id": None,
                },
            },
            {
                "index": 2,
                "name": "Final Signoff",
                "required_role": "compliance",
                "mapped_step_indexes": [1],
                "gate_keys": ["compliance"],
                "baseline": {
                    "status": "ready",
                    "sla_hours": 6,
                    "projected_due_at": (now + timedelta(hours=6)).isoformat(),
                    "blockers": [],
                    "required_actions": [],
                    "auto_triggers": [],
                    "assignee_id": user_id,
                    "delegate_id": None,
                },
                "simulated": {
                    "status": "ready",
                    "sla_hours": 5,
                    "projected_due_at": (now + timedelta(hours=5)).isoformat(),
                    "blockers": [],
                    "required_actions": [],
                    "auto_triggers": [],
                    "assignee_id": user_id,
                    "delegate_id": None,
                },
            },
        ],
    }

    response = client.post(
        "/api/governance/guardrails/simulations",
        json=request_payload,
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["summary"]["state"] == "clear"
    assert payload["summary"]["reasons"] == []
    assert payload["projected_delay_minutes"] == 0

    record_id = payload["id"]

    listing = client.get(
        f"/api/governance/guardrails/simulations?execution_id={execution_id}",
        headers=headers,
    )
    assert listing.status_code == 200, listing.text
    records = listing.json()
    matched = next((item for item in records if item["id"] == record_id), None)
    assert matched is not None
    assert matched["summary"]["state"] == "clear"
    assert matched["summary"]["reasons"] == []

    db = TestingSessionLocal()
    try:
        stored = (
            db.query(models.GovernanceGuardrailSimulation)
            .filter(models.GovernanceGuardrailSimulation.id == uuid.UUID(record_id))
            .first()
        )
        assert stored is not None
        assert stored.state == "clear"
        assert stored.summary["reasons"] == []
        assert stored.projected_delay_minutes == 0
    finally:
        db.close()
