from datetime import datetime, timezone, timedelta
import io
import json
import uuid
import zipfile
from datetime import datetime, timedelta, timezone

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


def create_user_headers(email: str | None = None):
    """Create a user in the test database and return auth headers and metadata."""

    email = email or f"{uuid.uuid4()}@example.com"
    token = create_access_token({"sub": email})
    db = TestingSessionLocal()
    try:
        user = models.User(email=email, hashed_password="placeholder")
        db.add(user)
        db.commit()
        user_id = user.id
    finally:
        db.close()
    return {"Authorization": f"Bearer {token}"}, user_id, email


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
    assert any(
        event["event_type"] == "session.created"
        for event in session_payload.get("timeline_preview", [])
    )

    exec_id = session_payload["execution"]["id"]

    fetched = client.get(
        f"/api/experiment-console/sessions/{exec_id}", headers=headers
    )
    assert fetched.status_code == 200
    assert fetched.json()["execution"]["id"] == exec_id

    timeline_initial = client.get(
        f"/api/experiment-console/sessions/{exec_id}/timeline",
        headers=headers,
    )
    assert timeline_initial.status_code == 200
    timeline_payload = timeline_initial.json()
    assert timeline_payload["events"][0]["event_type"] == "session.created"
    assert timeline_payload["next_cursor"] is None

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

    timeline_after = client.get(
        f"/api/experiment-console/sessions/{exec_id}/timeline",
        headers=headers,
    ).json()
    event_types = [event["event_type"] for event in timeline_after["events"]]
    assert "step.transition" in event_types


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


def test_generate_execution_narrative_export(client):
    headers = get_headers(client)

    template = client.post(
        "/api/protocols/templates",
        json={"name": "Narrative Protocol", "content": "Prep\nExecute"},
        headers=headers,
    ).json()

    created = client.post(
        "/api/experiment-console/sessions",
        json={"template_id": template["id"], "title": "Narrative Run"},
        headers=headers,
    ).json()

    exec_id = created["execution"]["id"]

    now = datetime.now(timezone.utc)
    client.post(
        f"/api/experiment-console/sessions/{exec_id}/steps/0",
        json={
            "status": "completed",
            "started_at": now.isoformat(),
            "completed_at": now.isoformat(),
        },
        headers=headers,
    )

    timeline_seed = client.get(
        f"/api/experiment-console/sessions/{exec_id}/timeline",
        headers=headers,
    ).json()
    assert timeline_seed["events"], "expected initial timeline events for attachment selection"
    attachment_event_id = timeline_seed["events"][0]["id"]

    export_resp = client.post(
        f"/api/experiment-console/sessions/{exec_id}/exports/narrative",
        json={
            "notes": "Compliance evidence bundle",
            "metadata": {"ticket": "QC-21"},
            "attachments": [
                {"event_id": attachment_event_id, "label": "Session created"}
            ],
        },
        headers=headers,
    )
    assert export_resp.status_code == 200
    payload = export_resp.json()
    assert payload["format"] == "markdown"
    assert payload["event_count"] >= 1
    assert payload["notes"] == "Compliance evidence bundle"
    assert payload["metadata"]["ticket"] == "QC-21"
    assert payload["approval_status"] == "pending"
    assert payload["approval_stage_count"] == 1
    assert payload["approval_stages"][0]["status"] == "in_progress"
    assert payload["current_stage"]["sequence_index"] == 1
    assert payload["version"] == 1
    assert payload["attachments"], "expected attachment to be persisted"
    assert payload["attachments"][0]["reference_id"] == attachment_event_id
    assert f"execution_id: `{exec_id}`" in payload["content"]
    assert "session.created" in payload["content"]
    assert payload["artifact_status"] in {"queued", "processing", "ready"}
    if payload["artifact_status"] == "ready":
        assert payload["artifact_download_path"]
        assert payload["artifact_signed_url"]
        assert payload["packaging_attempts"] >= 1
    else:
        assert payload["artifact_download_path"] is None
        assert payload["artifact_signed_url"] is None

    history = client.get(
        f"/api/experiment-console/sessions/{exec_id}/exports/narrative",
        headers=headers,
    )
    assert history.status_code == 200
    exports = history.json()["exports"]
    assert len(exports) == 1
    assert exports[0]["id"] == payload["id"]
    assert exports[0]["artifact_status"] in {"queued", "processing", "retrying", "ready"}
    if exports[0]["artifact_status"] == "ready":
        assert exports[0]["artifact_file"] is not None
        assert exports[0]["artifact_checksum"]
        assert exports[0]["artifact_download_path"]
        assert exports[0]["artifact_signed_url"]
        assert exports[0]["packaged_at"]
        assert exports[0]["retention_expires_at"]

        artifact_resp = client.get(exports[0]["artifact_download_path"], headers=headers)
        assert artifact_resp.status_code == 200
        assert artifact_resp.headers["content-type"] == "application/zip"
        assert artifact_resp.content.startswith(b"PK"), "expected zip file signature"
    else:
        assert exports[0]["artifact_file"] is None

    second_export = client.post(
        f"/api/experiment-console/sessions/{exec_id}/exports/narrative",
        json={"notes": "QA rerun"},
        headers=headers,
    ).json()
    assert second_export["version"] == 2
    assert second_export["artifact_status"] in {"queued", "processing", "ready"}

    approval_resp = client.post(
        f"/api/experiment-console/sessions/{exec_id}/exports/narrative/{second_export['id']}/approve",
        json={"status": "approved", "signature": "QA ✅"},
        headers=headers,
    )
    assert approval_resp.status_code == 200
    approved_payload = approval_resp.json()
    assert approved_payload["approval_status"] == "approved"
    assert approved_payload["approval_signature"] == "QA ✅"
    assert approved_payload["approved_at"] is not None
    assert approved_payload["artifact_download_path"]
    if approved_payload["artifact_status"] == "ready":
        assert approved_payload["artifact_signed_url"]

    timeline = client.get(
        f"/api/experiment-console/sessions/{exec_id}/timeline",
        headers=headers,
    ).json()
    assert any(event["event_type"] == "narrative_export.created" for event in timeline["events"])
    assert any(event["event_type"].startswith("narrative_export.packaging") for event in timeline["events"])
    assert any(event["event_type"] == "narrative_export.approval.stage_completed" for event in timeline["events"])
    assert any(event["event_type"] == "narrative_export.approval.finalized" for event in timeline["events"])

    jobs_snapshot = client.get(
        "/api/experiment-console/exports/narrative/jobs",
        headers=headers,
    ).json()
    assert "queue" in jobs_snapshot
    assert "status_counts" in jobs_snapshot


def test_narrative_export_with_multidomain_evidence(client):
    headers = get_headers(client)

    template = client.post(
        "/api/protocols/templates",
        json={"name": "Evidence Protocol", "content": "Prep\nCapture"},
        headers=headers,
    ).json()

    session = client.post(
        "/api/experiment-console/sessions",
        json={"template_id": template["id"], "title": "Evidence Run"},
        headers=headers,
    ).json()

    exec_id = session["execution"]["id"]

    timeline_seed = client.get(
        f"/api/experiment-console/sessions/{exec_id}/timeline",
        headers=headers,
    ).json()
    assert timeline_seed["events"]
    primary_event_id = timeline_seed["events"][0]["id"]

    notebook_entry = client.post(
        "/api/notebook/entries",
        json={"title": "Run Notes", "content": "Observations"},
        headers=headers,
    ).json()

    db = TestingSessionLocal()
    try:
        exec_uuid = uuid.UUID(exec_id)
        now = datetime.now(timezone.utc)
        analytics_event = models.ExecutionEvent(
            execution_id=exec_uuid,
            event_type="analytics.snapshot.secondary",
            payload={"label": "Secondary Snapshot", "metrics": {"yield": {"value": 0.88}}},
            sequence=210,
            created_at=now,
        )
        qc_event = models.ExecutionEvent(
            execution_id=exec_uuid,
            event_type="qc.metric.calibration",
            payload={"label": "Calibration", "readings": [{"name": "OD", "value": 0.42}]},
            sequence=211,
            created_at=now,
        )
        remediation_event = models.ExecutionEvent(
            execution_id=exec_uuid,
            event_type="remediation.report.followup",
            payload={"label": "Follow up", "actions": ["notify:team"]},
            sequence=212,
            created_at=now,
        )
        db.add_all([analytics_event, qc_event, remediation_event])
        db.commit()
        analytics_id = str(analytics_event.id)
        qc_id = str(qc_event.id)
        remediation_id = str(remediation_event.id)
    finally:
        db.close()

    export_resp = client.post(
        f"/api/experiment-console/sessions/{exec_id}/exports/narrative",
        json={
            "notes": "Multi-domain bundle",
            "attachments": [
                {"event_id": primary_event_id, "label": "Session created"},
                {
                    "type": "notebook_entry",
                    "reference_id": notebook_entry["id"],
                    "context": {"include_content": True},
                },
                {
                    "type": "analytics_snapshot",
                    "reference_id": analytics_id,
                },
                {
                    "type": "qc_metric",
                    "reference_id": qc_id,
                },
                {
                    "type": "remediation_report",
                    "reference_id": remediation_id,
                    "context": {"audience": "compliance"},
                },
            ],
        },
        headers=headers,
    )
    assert export_resp.status_code == 200
    export_payload = export_resp.json()
    assert len(export_payload["attachments"]) == 5
    evidence_types = {item["evidence_type"] for item in export_payload["attachments"]}
    assert "notebook_entry" in evidence_types
    assert "analytics_snapshot" in evidence_types
    assert "qc_metric" in evidence_types
    assert "remediation_report" in evidence_types

    history_snapshot = client.get(
        f"/api/experiment-console/sessions/{exec_id}/exports/narrative",
        headers=headers,
    ).json()
    export_record = next(
        item for item in history_snapshot["exports"] if item["id"] == export_payload["id"]
    )
    if export_record["artifact_download_path"]:
        artifact_resp = client.get(export_record["artifact_download_path"], headers=headers)
        assert artifact_resp.status_code == 200
        archive = zipfile.ZipFile(io.BytesIO(artifact_resp.content))
        manifest = json.loads(archive.read("attachments.json").decode("utf-8"))
        manifest_types = {entry["type"] for entry in manifest}
        assert "notebook_entry" in manifest_types
        assert "analytics_snapshot" in manifest_types
        assert "qc_metric" in manifest_types
        assert "remediation_report" in manifest_types
        analytics_entry = next(entry for entry in manifest if entry["type"] == "analytics_snapshot")
        assert analytics_entry["event"]["payload_path"].endswith(".json")
        notebook_entry_manifest = next(entry for entry in manifest if entry["type"] == "notebook_entry")
        assert notebook_entry_manifest["notebook"]["path"].endswith(".md")
        archive.close()

def test_multistage_approval_delegation_and_reset(client):
    headers = get_headers(client)

    template = client.post(
        "/api/protocols/templates",
        json={"name": "Staged Approval", "content": "Prep\nReview"},
        headers=headers,
    ).json()

    execution = client.post(
        "/api/experiment-console/sessions",
        json={"template_id": template["id"], "title": "Staged Run"},
        headers=headers,
    ).json()

    exec_id = execution["execution"]["id"]

    export_payload = client.post(
        f"/api/experiment-console/sessions/{exec_id}/exports/narrative",
        json={
            "approval_stages": [
                {"name": "Scientist Review", "required_role": "scientist", "sla_hours": 1},
                {"name": "QA Review", "required_role": "qa", "sla_hours": 2},
            ]
        },
        headers=headers,
    ).json()

    assert export_payload["approval_stage_count"] == 2
    assert export_payload["current_stage"]["name"] == "Scientist Review"
    first_stage_id = export_payload["current_stage"]["id"]
    second_stage_id = next(
        stage["id"]
        for stage in export_payload["approval_stages"]
        if stage["sequence_index"] == 2
    )

    approve_first = client.post(
        f"/api/experiment-console/sessions/{exec_id}/exports/narrative/{export_payload['id']}/approve",
        json={"status": "approved", "signature": "Scientist ✅", "stage_id": first_stage_id},
        headers=headers,
    )
    assert approve_first.status_code == 200
    progressed = approve_first.json()
    assert progressed["current_stage"]["id"] == second_stage_id
    assert progressed["approval_status"] == "pending"

    me = client.get("/api/users/me", headers=headers).json()
    delegated = client.post(
        f"/api/experiment-console/sessions/{exec_id}/exports/narrative/{export_payload['id']}/stages/{second_stage_id}/delegate",
        json={"delegate_id": me["id"], "notes": "Covering QA"},
        headers=headers,
    )
    assert delegated.status_code == 200
    ladder = delegated.json()
    stage_two = next(stage for stage in ladder["approval_stages"] if stage["id"] == second_stage_id)
    assert stage_two["delegated_to"]["id"] == me["id"]

    db = TestingSessionLocal()
    try:
        stage_obj = (
            db.query(models.ExecutionNarrativeApprovalStage)
            .filter(models.ExecutionNarrativeApprovalStage.id == uuid.UUID(second_stage_id))
            .first()
        )
        stage_obj.due_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()
    finally:
        db.close()

    from app.tasks import monitor_narrative_approval_slas

    monitor_narrative_approval_slas()

    timeline = client.get(
        f"/api/experiment-console/sessions/{exec_id}/timeline",
        headers=headers,
    ).json()["events"]
    assert any(event["event_type"] == "narrative_export.approval.stage_overdue" for event in timeline)

    db = TestingSessionLocal()
    try:
        stage_obj = (
            db.query(models.ExecutionNarrativeApprovalStage)
            .filter(models.ExecutionNarrativeApprovalStage.id == uuid.UUID(second_stage_id))
            .first()
        )
        assert stage_obj is not None
        assert stage_obj.meta.get("overdue") is True
        assert any(action.action_type == "escalated" for action in stage_obj.actions)
        notifications = (
            db.query(models.Notification)
            .filter(models.Notification.user_id == uuid.UUID(me["id"]))
            .all()
        )
        assert any("overdue" in note.message.lower() for note in notifications)
    finally:
        db.close()

    reset_resp = client.post(
        f"/api/experiment-console/sessions/{exec_id}/exports/narrative/{export_payload['id']}/stages/{second_stage_id}/reset",
        json={"notes": "Remediate QA"},
        headers=headers,
    )
    assert reset_resp.status_code == 200
    reset_payload = reset_resp.json()
    reset_stage = next(stage for stage in reset_payload["approval_stages"] if stage["id"] == second_stage_id)
    assert reset_stage["status"] == "in_progress"
    assert reset_payload["approval_status"] == "pending"

    rejection = client.post(
        f"/api/experiment-console/sessions/{exec_id}/exports/narrative/{export_payload['id']}/approve",
        json={"status": "rejected", "signature": "QA ❌", "stage_id": second_stage_id},
        headers=headers,
    )
    assert rejection.status_code == 200
    rejected_payload = rejection.json()
    assert rejected_payload["approval_status"] == "rejected"
    final_stage = next(stage for stage in rejected_payload["approval_stages"] if stage["id"] == second_stage_id)
    assert final_stage["status"] == "rejected"

    final_timeline = client.get(
        f"/api/experiment-console/sessions/{exec_id}/timeline",
        headers=headers,
    ).json()["events"]
    assert any(event["event_type"] == "narrative_export.approval.rejected" for event in final_timeline)


def test_narrative_export_packaging_blocked_until_final_stage(client):
    headers, user_id, _ = create_user_headers()

    template = client.post(
        "/api/protocols/templates",
        json={"name": "Two-Stage", "content": "Step"},
        headers=headers,
    ).json()

    session = client.post(
        "/api/experiment-console/sessions",
        json={"template_id": template["id"], "title": "Two Stage Execution"},
        headers=headers,
    ).json()

    execution_id = session["execution"]["id"]

    export = client.post(
        f"/api/experiment-console/sessions/{execution_id}/exports/narrative",
        json={
            "notes": "Two stage export",
            "approval_stages": [
                {"required_role": "scientist", "name": "Stage 1", "sla_hours": 1, "assignee_id": str(user_id)},
                {"required_role": "qa", "name": "Stage 2", "sla_hours": 2},
            ],
        },
        headers=headers,
    ).json()

    export_id = export["id"]
    stage_ids = [stage["id"] for stage in export["approval_stages"]]

    assert export["approval_status"] == "pending"
    assert export["artifact_status"] == "queued"

    timeline = client.get(
        f"/api/experiment-console/sessions/{execution_id}/timeline",
        headers=headers,
    ).json()

    assert any(
        event["event_type"] == "narrative_export.packaging.awaiting_approval"
        for event in timeline["events"]
    )

    db = TestingSessionLocal()
    try:
        export_row = (
            db.query(models.ExecutionNarrativeExport)
            .filter(models.ExecutionNarrativeExport.id == uuid.UUID(export_id))
            .first()
        )
        assert export_row is not None
        assert export_row.packaging_attempts == 0
        assert export_row.artifact_file_id is None
    finally:
        db.close()

    first_stage_response = client.post(
        f"/api/experiment-console/sessions/{execution_id}/exports/narrative/{export_id}/approve",
        json={"status": "approved", "signature": "Stage 1", "stage_id": stage_ids[0]},
        headers=headers,
    )
    assert first_stage_response.status_code == 200, first_stage_response.text

    db = TestingSessionLocal()
    try:
        export_row = (
            db.query(models.ExecutionNarrativeExport)
            .filter(models.ExecutionNarrativeExport.id == uuid.UUID(export_id))
            .first()
        )
        assert export_row is not None
        assert export_row.packaging_attempts == 0
        assert export_row.artifact_file_id is None
    finally:
        db.close()

    final_stage_response = client.post(
        f"/api/experiment-console/sessions/{execution_id}/exports/narrative/{export_id}/approve",
        json={"status": "approved", "signature": "Stage 2", "stage_id": stage_ids[1]},
        headers=headers,
    )
    assert final_stage_response.status_code == 200, final_stage_response.text

    db = TestingSessionLocal()
    try:
        export_row = (
            db.query(models.ExecutionNarrativeExport)
            .filter(models.ExecutionNarrativeExport.id == uuid.UUID(export_id))
            .first()
        )
        assert export_row is not None
        assert export_row.packaging_attempts >= 1
        assert export_row.artifact_file_id is not None
        assert export_row.artifact_status == "ready"
    finally:
        db.close()

    timeline_after = client.get(
        f"/api/experiment-console/sessions/{execution_id}/timeline",
        headers=headers,
    ).json()
    assert any(
        event["event_type"] == "narrative_export.packaging.ready"
        for event in timeline_after["events"]
    )


def _create_preview_snapshot(template_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    db = TestingSessionLocal()
    try:
        user = db.query(models.User).order_by(models.User.created_at.desc()).first()
        if not user:
            user = models.User(email=f"{uuid.uuid4()}@example.com", hashed_password="placeholder")
            db.add(user)
            db.flush()
        template_key = f"governance.baseline.{uuid.uuid4()}"
        workflow_template = models.ExecutionNarrativeWorkflowTemplate(
            template_key=template_key,
            name="Baseline",
            description="",
            version=1,
            stage_blueprint=[{"required_role": "scientist", "name": "Review"}],
            default_stage_sla_hours=48,
            permitted_roles=["scientist"],
            status="published",
            created_by_id=user.id if user else None,
        )
        db.add(workflow_template)
        db.flush()

        snapshot = models.ExecutionNarrativeWorkflowTemplateSnapshot(
            template_id=workflow_template.id,
            template_key=template_key,
            version=1,
            status="published",
            captured_by_id=user.id if user else None,
            snapshot_payload={
                "default_stage_sla_hours": 48,
                "stage_blueprint": [
                    {
                        "required_role": "scientist",
                        "name": "Review",
                        "sla_hours": 48,
                        "metadata": {},
                    }
                ],
            },
        )
        db.add(snapshot)
        db.flush()

        assignment = models.ExecutionNarrativeWorkflowTemplateAssignment(
            template_id=workflow_template.id,
            protocol_template_id=template_id,
            created_by_id=user.id,
        )
        db.add(assignment)
        db.commit()
        return workflow_template.id, snapshot.id
    finally:
        db.close()


def test_scenario_workspace_crud_flow(client):
    headers = get_headers(client)

    template = client.post(
        "/api/protocols/templates",
        json={"name": "Scenario Protocol", "content": "Prep"},
        headers=headers,
    ).json()

    session_payload = client.post(
        "/api/experiment-console/sessions",
        json={"template_id": template["id"]},
        headers=headers,
    ).json()

    execution_id = session_payload["execution"]["id"]
    template_uuid = uuid.UUID(template["id"])
    _, snapshot_id = _create_preview_snapshot(template_uuid)

    workspace = client.get(
        f"/api/experiments/{execution_id}/scenarios",
        headers=headers,
    )
    assert workspace.status_code == 200
    workspace_payload = workspace.json()
    assert workspace_payload["scenarios"] == []
    assert workspace_payload["folders"] == []
    snapshot_ids = {entry["id"] for entry in workspace_payload["snapshots"]}
    assert str(snapshot_id) in snapshot_ids

    create_resp = client.post(
        f"/api/experiments/{execution_id}/scenarios",
        json={
            "name": "Baseline Check",
            "description": "confirm baseline",
            "workflow_template_snapshot_id": str(snapshot_id),
            "stage_overrides": [{"index": 0, "sla_hours": 72}],
            "resource_overrides": {"inventory_item_ids": []},
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    scenario_payload = create_resp.json()
    assert scenario_payload["name"] == "Baseline Check"
    assert scenario_payload["stage_overrides"][0]["sla_hours"] == 72
    assert scenario_payload["folder_id"] is None
    assert scenario_payload["is_shared"] is False
    assert scenario_payload["shared_team_ids"] == []
    assert scenario_payload["expires_at"] is None
    assert scenario_payload["timeline_event_id"] is None

    updated = client.put(
        f"/api/experiments/{execution_id}/scenarios/{scenario_payload['id']}",
        json={
            "name": "Updated Scenario",
            "stage_overrides": [
                {
                    "index": 0,
                    "sla_hours": 60,
                    "assignee_id": scenario_payload["owner_id"],
                }
            ],
        },
        headers=headers,
    )
    assert updated.status_code == 200
    updated_payload = updated.json()
    assert updated_payload["name"] == "Updated Scenario"
    assert updated_payload["stage_overrides"][0]["sla_hours"] == 60
    assert updated_payload["stage_overrides"][0]["assignee_id"] == scenario_payload["owner_id"]
    assert updated_payload["is_shared"] is False

    clone_resp = client.post(
        f"/api/experiments/{execution_id}/scenarios/{scenario_payload['id']}/clone",
        json={"name": "Cloned"},
        headers=headers,
    )
    assert clone_resp.status_code == 201
    clone_payload = clone_resp.json()
    assert clone_payload["cloned_from_id"] == scenario_payload["id"]
    assert clone_payload["stage_overrides"][0]["sla_hours"] == 60

    delete_resp = client.delete(
        f"/api/experiments/{execution_id}/scenarios/{scenario_payload['id']}",
        headers=headers,
    )
    assert delete_resp.status_code == 204

    final_workspace = client.get(
        f"/api/experiments/{execution_id}/scenarios",
        headers=headers,
    ).json()
    assert len(final_workspace["scenarios"]) == 1
    assert final_workspace["scenarios"][0]["name"] == "Cloned"


def test_scenario_workspace_rbac_blocks_other_users(client):
    owner_headers = get_headers(client)

    template = client.post(
        "/api/protocols/templates",
        json={"name": "RBAC Protocol", "content": "Prep"},
        headers=owner_headers,
    ).json()

    template_uuid = uuid.UUID(template["id"])
    _, snapshot_id = _create_preview_snapshot(template_uuid)

    session_payload = client.post(
        "/api/experiment-console/sessions",
        json={"template_id": template["id"]},
        headers=owner_headers,
    ).json()
    execution_id = session_payload["execution"]["id"]
    template_uuid = uuid.UUID(template["id"])
    _, snapshot_id = _create_preview_snapshot(template_uuid)

    create_resp = client.post(
        f"/api/experiments/{execution_id}/scenarios",
        json={
            "name": "Owner Scenario",
            "workflow_template_snapshot_id": str(snapshot_id),
        },
        headers=owner_headers,
    )
    assert create_resp.status_code == 201
    scenario_id = create_resp.json()["id"]

    other_headers = get_headers(client)

    list_attempt = client.get(
        f"/api/experiments/{execution_id}/scenarios",
        headers=other_headers,
    )
    assert list_attempt.status_code == 403

    update_attempt = client.put(
        f"/api/experiments/{execution_id}/scenarios/{scenario_id}",
        json={"name": "Unauthorised"},
        headers=other_headers,
    )
    assert update_attempt.status_code == 403


def test_shared_scenario_visibility_and_expiry(client):
    owner_headers, owner_id, _ = create_user_headers("owner@example.com")
    reviewer_headers, reviewer_id, _ = create_user_headers("reviewer@example.com")
    outsider_headers, _outsider_id, _ = create_user_headers("outsider@example.com")

    db = TestingSessionLocal()
    try:
        team = models.Team(name="Governance")
        db.add(team)
        db.flush()
        db.add_all(
            [
                models.TeamMember(team_id=team.id, user_id=owner_id, role="lead"),
                models.TeamMember(team_id=team.id, user_id=reviewer_id, role="reviewer"),
            ]
        )
        db.commit()
        team_id = team.id
    finally:
        db.close()

    template = client.post(
        "/api/protocols/templates",
        json={"name": "Shared Protocol", "content": "Prep"},
        headers=owner_headers,
    ).json()

    template_uuid = uuid.UUID(template["id"])
    _, snapshot_id = _create_preview_snapshot(template_uuid)

    session_payload = client.post(
        "/api/experiment-console/sessions",
        json={"template_id": template["id"]},
        headers=owner_headers,
    ).json()
    execution_id = session_payload["execution"]["id"]

    db = TestingSessionLocal()
    try:
        template_row = db.get(models.ProtocolTemplate, uuid.UUID(template["id"]))
        template_row.team_id = team_id
        db.add(template_row)
        db.flush()

        execution_row = db.get(models.ProtocolExecution, uuid.UUID(execution_id))
        execution_row.run_by = owner_id
        db.add(execution_row)
        db.flush()

        event = models.ExecutionEvent(
            execution_id=execution_row.id,
            event_type="session.annotated",
            payload={"note": "Initial analysis"},
            actor_id=owner_id,
            sequence=99,
        )
        db.add(event)
        db.commit()
        event_id = str(event.id)
    finally:
        db.close()

    folder_resp = client.post(
        f"/api/experiments/{execution_id}/scenario-folders",
        json={
            "name": "Team Reviews",
            "description": "Shared folder",
            "visibility": "team",
            "team_id": str(team_id),
        },
        headers=owner_headers,
    )
    assert folder_resp.status_code == 201
    folder_payload = folder_resp.json()

    future_expiry = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    create_resp = client.post(
        f"/api/experiments/{execution_id}/scenarios",
        json={
            "name": "Shared Scenario",
            "workflow_template_snapshot_id": str(snapshot_id),
            "folder_id": folder_payload["id"],
            "is_shared": True,
            "shared_team_ids": [str(team_id)],
            "expires_at": future_expiry,
            "timeline_event_id": event_id,
        },
        headers=owner_headers,
    )
    assert create_resp.status_code == 201
    scenario_payload = create_resp.json()
    assert scenario_payload["folder_id"] == folder_payload["id"]
    assert scenario_payload["is_shared"] is True
    assert scenario_payload["shared_team_ids"] == [str(team_id)]
    assert scenario_payload["timeline_event_id"] == event_id

    past_expiry = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    expired_resp = client.post(
        f"/api/experiments/{execution_id}/scenarios",
        json={
            "name": "Expired Scenario",
            "workflow_template_snapshot_id": scenario_payload["workflow_template_snapshot_id"],
            "expires_at": past_expiry,
        },
        headers=owner_headers,
    )
    assert expired_resp.status_code == 201

    reviewer_workspace = client.get(
        f"/api/experiments/{execution_id}/scenarios",
        headers=reviewer_headers,
    )
    assert reviewer_workspace.status_code == 200
    reviewer_payload = reviewer_workspace.json()
    returned_ids = {entry["id"] for entry in reviewer_payload["scenarios"]}
    assert scenario_payload["id"] in returned_ids
    assert reviewer_payload["folders"][0]["id"] == folder_payload["id"]
    assert all(entry["name"] != "Expired Scenario" for entry in reviewer_payload["scenarios"])

    outsider_workspace = client.get(
        f"/api/experiments/{execution_id}/scenarios",
        headers=outsider_headers,
    )
    assert outsider_workspace.status_code == 403
