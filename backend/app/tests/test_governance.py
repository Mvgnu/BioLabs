import uuid

from app import models
from app.auth import create_access_token
from app.tests.conftest import TestingSessionLocal


def admin_headers():
    email = f"admin-{uuid.uuid4()}@example.com"
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


def test_template_creation_and_versioning(client):
    headers, _ = admin_headers()

    first_payload = {
        "template_key": "biosafety",
        "name": "Biosafety Ladder",
        "description": "Baseline biosafety approval ladder",
        "default_stage_sla_hours": 48,
        "permitted_roles": ["qa_lead", "compliance"],
        "stage_blueprint": [
            {"name": "QA Review", "required_role": "qa_lead", "sla_hours": 24},
            {"name": "Compliance", "required_role": "compliance"},
        ],
        "publish": True,
    }

    first_response = client.post(
        "/api/governance/templates",
        json=first_payload,
        headers=headers,
    )
    assert first_response.status_code == 201
    first_template = first_response.json()
    assert first_template["version"] == 1
    assert first_template["status"] == "published"
    assert first_template["is_latest"] is True
    assert len(first_template["stage_blueprint"]) == 2
    assert first_template["published_snapshot_id"] is not None

    second_payload = {
        "template_key": "biosafety",
        "name": "Biosafety Ladder",
        "description": "Refined biosafety approvals",
        "default_stage_sla_hours": 72,
        "permitted_roles": ["qa_lead", "compliance", "safety_officer"],
        "stage_blueprint": [
            {"name": "QA Review", "required_role": "qa_lead", "sla_hours": 24},
            {"name": "Safety", "required_role": "safety_officer", "sla_hours": 24},
            {"name": "Compliance", "required_role": "compliance"},
        ],
        "publish": False,
        "forked_from_id": first_template["id"],
    }

    second_response = client.post(
        "/api/governance/templates",
        json=second_payload,
        headers=headers,
    )
    assert second_response.status_code == 201
    second_template = second_response.json()
    assert second_template["version"] == 2
    assert second_template["status"] == "draft"
    assert second_template["forked_from_id"] == first_template["id"]
    assert second_template["is_latest"] is True

    detail_response = client.get(
        f"/api/governance/templates/{first_template['id']}",
        headers=headers,
    )
    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload["is_latest"] is False



def test_export_creation_uses_template_blueprint(client):
    headers, user_id = admin_headers()

    template_payload = {
        "template_key": "compliance",
        "name": "Compliance Ladder",
        "description": "Two-step compliance approval",
        "default_stage_sla_hours": 36,
        "permitted_roles": ["qa_lead", "compliance"],
        "stage_blueprint": [
            {"name": "QA", "required_role": "qa_lead", "sla_hours": 12},
            {"name": "Compliance", "required_role": "compliance"},
        ],
        "publish": True,
    }
    template_resp = client.post(
        "/api/governance/templates",
        json=template_payload,
        headers=headers,
    )
    template_id = template_resp.json()["id"]

    db = TestingSessionLocal()
    try:
        protocol_template = models.ProtocolTemplate(
            name="Test Protocol",
            content="Step 1\nStep 2",
            created_by=user_id,
        )
        db.add(protocol_template)
        db.flush()

        execution = models.ProtocolExecution(
            template_id=protocol_template.id,
            run_by=user_id,
            status="completed",
            params={},
            result={},
        )
        db.add(execution)
        db.flush()

        event = models.ExecutionEvent(
            execution_id=execution.id,
            event_type="session.created",
            payload={"note": "Started"},
            actor_id=user_id,
            sequence=1,
        )
        db.add(event)
        db.commit()
        execution_id = execution.id
    finally:
        db.close()

    publish_resp = client.post(
        f"/api/governance/templates/{template_id}/publish",
        headers=headers,
    )
    assert publish_resp.status_code == 200
    snapshot_id = publish_resp.json()["published_snapshot_id"]
    assert snapshot_id

    export_response = client.post(
        f"/api/experiment-console/sessions/{execution_id}/exports/narrative",
        json={
            "workflow_template_id": template_id,
            "workflow_template_snapshot_id": snapshot_id,
        },
        headers=headers,
    )
    assert export_response.status_code == 200
    export_payload = export_response.json()
    assert export_payload["workflow_template_id"] == template_id
    assert export_payload["workflow_template_version"] == 1
    assert export_payload["workflow_template_key"] == "compliance"
    assert export_payload["approval_stage_count"] == 2
    assert export_payload["approval_stages"][0]["required_role"] == "qa_lead"
    assert export_payload["approval_stages"][1]["required_role"] == "compliance"
    snapshot = export_payload["workflow_template_snapshot"]
    assert export_payload["workflow_template_snapshot_id"] == snapshot_id
    assert snapshot["stage_blueprint"][0]["name"] == "QA"
    assert snapshot["template_key"] == "compliance"
