import uuid
from datetime import datetime, timedelta, timezone

from app import models
from app.auth import create_access_token
from .conftest import TestingSessionLocal


def create_admin_headers():
    email = f"admin+{uuid.uuid4()}@example.com"
    token = create_access_token({"sub": email})
    db = TestingSessionLocal()
    try:
        user = models.User(email=email, hashed_password="placeholder", is_admin=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = str(user.id)
    finally:
        db.close()
    return {"Authorization": f"Bearer {token}"}, user_id


def test_governance_ladder_endpoints_flow(client):
    headers, admin_id = create_admin_headers()

    template = client.post(
        "/api/protocols/templates",
        json={"name": "Governance Ladder", "content": "Step"},
        headers=headers,
    ).json()

    execution = client.post(
        "/api/experiment-console/sessions",
        json={"template_id": template["id"], "title": "Governance Run"},
        headers=headers,
    ).json()

    execution_id = execution["execution"]["id"]

    export = client.post(
        f"/api/experiment-console/sessions/{execution_id}/exports/narrative",
        json={
            "approval_stages": [
                {"required_role": "scientist", "name": "Scientist Review", "sla_hours": 1},
                {"required_role": "qa", "name": "QA Review", "sla_hours": 2},
            ]
        },
        headers=headers,
    ).json()

    export_id = export["id"]
    first_stage_id = export["approval_stages"][0]["id"]
    second_stage_id = export["approval_stages"][1]["id"]

    now = datetime.now(timezone.utc)
    simulation_payload = {
        "execution_id": execution_id,
        "metadata": {"scenario": "qa-blocked"},
        "comparisons": [
            {
                "index": 0,
                "name": "Scientist Review",
                "required_role": "scientist",
                "baseline": {
                    "status": "ready",
                    "sla_hours": 1,
                    "projected_due_at": (now + timedelta(hours=1)).isoformat(),
                    "blockers": [],
                    "required_actions": [],
                    "auto_triggers": [],
                    "assignee_id": admin_id,
                    "delegate_id": None,
                },
                "simulated": {
                    "status": "pending",
                    "sla_hours": 3,
                    "projected_due_at": (now + timedelta(hours=3)).isoformat(),
                    "blockers": ["awaiting-evidence"],
                    "required_actions": ["notify:qa"],
                    "auto_triggers": [],
                    "assignee_id": admin_id,
                    "delegate_id": None,
                },
            }
        ],
    }
    simulation_response = client.post(
        "/api/governance/guardrails/simulations",
        json=simulation_payload,
        headers=headers,
    )
    assert simulation_response.status_code == 200, simulation_response.text
    simulation_data = simulation_response.json()
    assert simulation_data["summary"]["state"] == "blocked"

    ladder_response = client.get(
        f"/api/governance/exports/{export_id}", headers=headers
    )
    assert ladder_response.status_code == 200, ladder_response.text
    ladder_payload = ladder_response.json()
    assert ladder_payload["approval_stage_count"] == 2
    assert ladder_payload["approval_stages"][0]["status"] == "in_progress"
    assert ladder_payload["guardrail_simulation"]["id"] == simulation_data["id"]
    assert ladder_payload["guardrail_simulation"]["summary"]["state"] == "blocked"
    assert ladder_payload["guardrail_simulations"][0]["id"] == simulation_data["id"]

    delegate_response = client.post(
        f"/api/governance/exports/{export_id}/stages/{second_stage_id}/delegate",
        json={"delegate_id": admin_id, "notes": "QA cover"},
        headers=headers,
    )
    assert delegate_response.status_code == 200, delegate_response.text

    approved_first = client.post(
        f"/api/governance/exports/{export_id}/approve",
        json={"status": "approved", "signature": "Scientist", "stage_id": first_stage_id},
        headers=headers,
    )
    assert approved_first.status_code == 200, approved_first.text
    approved_first_payload = approved_first.json()
    assert approved_first_payload["current_stage"]["id"] == second_stage_id

    approved_final = client.post(
        f"/api/governance/exports/{export_id}/approve",
        json={"status": "approved", "signature": "QA", "stage_id": second_stage_id},
        headers=headers,
    )
    assert approved_final.status_code == 200, approved_final.text
    approved_final_payload = approved_final.json()
    assert approved_final_payload["approval_status"] == "approved"
    assert approved_final_payload["approval_stage_count"] == 2

    db = TestingSessionLocal()
    try:
        export_row = db.query(models.ExecutionNarrativeExport).filter(models.ExecutionNarrativeExport.id == uuid.UUID(export_id)).first()
        assert export_row is not None
        assert export_row.approval_status == "approved"
        assert export_row.approved_at is not None
    finally:
        db.close()


def test_governance_approve_dry_run_skips_enqueue(client, monkeypatch):
    headers, admin_id = create_admin_headers()

    template = client.post(
        "/api/protocols/templates",
        json={"name": "Governance Dry Run", "content": "Step"},
        headers=headers,
    ).json()

    session = client.post(
        "/api/experiment-console/sessions",
        json={"template_id": template["id"], "title": "Governance Dry"},
        headers=headers,
    ).json()

    execution_id = session["execution"]["id"]

    export = client.post(
        f"/api/experiment-console/sessions/{execution_id}/exports/narrative",
        json={
            "approval_stages": [
                {
                    "required_role": "qa",
                    "name": "QA",
                    "sla_hours": 1,
                    "assignee_id": admin_id,
                }
            ]
        },
        headers=headers,
    ).json()

    export_id = export["id"]
    stage_id = export["approval_stages"][0]["id"]

    enqueued: list[str] = []
    monkeypatch.setattr(
        "app.routes.governance_approvals.enqueue_narrative_export_packaging",
        lambda export_id: enqueued.append(str(export_id)),
    )

    def _fake_queue_state(db, *, export, actor=None):  # type: ignore[override]
        meta = dict(export.meta or {})
        meta["packaging_queue_state"] = {
            "event": "narrative_export.packaging.queued",
            "state": "queued",
        }
        export.meta = meta
        return True

    monkeypatch.setattr(
        "app.services.approval_ladders.record_packaging_queue_state",
        _fake_queue_state,
    )

    response = client.post(
        f"/api/governance/exports/{export_id}/approve",
        params={"dry_run": "true"},
        json={"status": "approved", "signature": "QA", "stage_id": stage_id},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["metadata"]["packaging_queue_state"]["state"] == "queued"
    assert enqueued == []


def test_governance_reset_stage(client):
    headers, _ = create_admin_headers()

    template = client.post(
        "/api/protocols/templates",
        json={"name": "Reset Ladder", "content": "Step"},
        headers=headers,
    ).json()

    execution = client.post(
        "/api/experiment-console/sessions",
        json={"template_id": template["id"], "title": "Reset Run"},
        headers=headers,
    ).json()

    execution_id = execution["execution"]["id"]

    export = client.post(
        f"/api/experiment-console/sessions/{execution_id}/exports/narrative",
        json={
            "approval_stages": [
                {"required_role": "scientist", "name": "Scientist Review", "sla_hours": 1},
                {"required_role": "qa", "name": "QA Review", "sla_hours": 2},
            ]
        },
        headers=headers,
    ).json()

    export_id = export["id"]
    first_stage_id = export["approval_stages"][0]["id"]
    second_stage_id = export["approval_stages"][1]["id"]

    first_stage_response = client.post(
        f"/api/governance/exports/{export_id}/approve",
        json={"status": "approved", "signature": "Scientist", "stage_id": first_stage_id},
        headers=headers,
    )
    assert first_stage_response.status_code == 200, first_stage_response.text

    reset_response = client.post(
        f"/api/governance/exports/{export_id}/stages/{second_stage_id}/reset",
        json={"notes": "Retry QA"},
        headers=headers,
    )
    assert reset_response.status_code == 200, reset_response.text
    reset_payload = reset_response.json()
    stage_two = next(stage for stage in reset_payload["approval_stages"] if stage["id"] == second_stage_id)
    assert stage_two["status"] == "in_progress"
    assert reset_payload["approval_status"] == "pending"

    db = TestingSessionLocal()
    try:
        export_row = db.query(models.ExecutionNarrativeExport).filter(models.ExecutionNarrativeExport.id == uuid.UUID(export_id)).first()
        assert export_row.current_stage_id == uuid.UUID(second_stage_id)
        assert export_row.approval_status == "pending"
        assert export_row.current_stage_started_at is not None
    finally:
        db.close()
