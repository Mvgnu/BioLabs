import uuid
from datetime import datetime, timezone

from app import models

from app.tests.conftest import TestingSessionLocal

from app.auth import create_access_token
from app.cli.migrate_templates import migrate_exports


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


def _create_team(db, name: str, creator_id: uuid.UUID) -> models.Team:
    team = models.Team(name=name, created_by=creator_id)
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


def test_publish_and_archive_cycle_excludes_archived(client):
    headers, _ = admin_headers()

    payload = {
        "template_key": "archive-check",
        "name": "Archive Check",
        "description": "Lifecycle validation",
        "default_stage_sla_hours": 24,
        "permitted_roles": ["qa_lead"],
        "stage_blueprint": [{"name": "QA", "required_role": "qa_lead"}],
        "publish": False,
    }
    create_resp = client.post("/api/governance/templates", json=payload, headers=headers)
    assert create_resp.status_code == 201
    template = create_resp.json()
    assert template["status"] == "draft"
    template_id = template["id"]

    publish_resp = client.post(f"/api/governance/templates/{template_id}/publish", headers=headers)
    assert publish_resp.status_code == 200
    published = publish_resp.json()
    assert published["status"] == "published"
    assert published["published_snapshot_id"] is not None

    archive_resp = client.post(f"/api/governance/templates/{template_id}/archive", headers=headers)
    assert archive_resp.status_code == 200
    archived = archive_resp.json()
    assert archived["status"] == "archived"
    assert archived["is_latest"] is False

    list_resp = client.get("/api/governance/templates", headers=headers)
    assert list_resp.status_code == 200
    returned_ids = {tpl["id"] for tpl in list_resp.json()}
    assert template_id not in returned_ids


def test_assignment_reassignment_requires_active_template(client):
    headers, user_id = admin_headers()

    template_payload = {
        "template_key": "assignment-check",
        "name": "Assignment Lifecycle",
        "description": "Assignment validation",
        "default_stage_sla_hours": 12,
        "permitted_roles": ["compliance"],
        "stage_blueprint": [{"name": "Compliance", "required_role": "compliance"}],
        "publish": True,
    }
    template_resp = client.post("/api/governance/templates", json=template_payload, headers=headers)
    template_id = template_resp.json()["id"]

    db = TestingSessionLocal()
    try:
        team = _create_team(db, "GovOps", user_id)
    finally:
        db.close()

    assignment_payload = {
        "template_id": template_id,
        "team_id": str(team.id),
    }
    assignment_resp = client.post(
        f"/api/governance/templates/{template_id}/assignments",
        json=assignment_payload,
        headers=headers,
    )
    assert assignment_resp.status_code == 201

    archive_resp = client.post(f"/api/governance/templates/{template_id}/archive", headers=headers)
    assert archive_resp.status_code == 200

    blocked_resp = client.post(
        f"/api/governance/templates/{template_id}/assignments",
        json=assignment_payload,
        headers=headers,
    )
    assert blocked_resp.status_code == 400

    successor_payload = {
        "template_key": "assignment-check",
        "name": "Assignment Lifecycle v2",
        "description": "Assignment validation v2",
        "default_stage_sla_hours": 18,
        "permitted_roles": ["compliance"],
        "stage_blueprint": [{"name": "Compliance", "required_role": "compliance"}],
        "publish": True,
        "forked_from_id": template_id,
    }
    successor_resp = client.post("/api/governance/templates", json=successor_payload, headers=headers)
    assert successor_resp.status_code == 201
    successor_id = successor_resp.json()["id"]

    reassignment_resp = client.post(
        f"/api/governance/templates/{successor_id}/assignments",
        json={"template_id": successor_id, "team_id": str(team.id)},
        headers=headers,
    )
    assert reassignment_resp.status_code == 201


def test_cli_migration_backfills_snapshot(client):
    headers, user_id = admin_headers()

    template_payload = {
        "template_key": "migration-check",
        "name": "Migration Template",
        "description": "Migration validation",
        "default_stage_sla_hours": 8,
        "permitted_roles": ["qa_lead"],
        "stage_blueprint": [{"name": "QA", "required_role": "qa_lead"}],
        "publish": True,
    }
    template_resp = client.post("/api/governance/templates", json=template_payload, headers=headers)
    template_data = template_resp.json()
    template_id = template_data["id"]
    snapshot_id = template_data["published_snapshot_id"]
    template_uuid = uuid.UUID(template_id)

    db = TestingSessionLocal()
    try:
        protocol_template = models.ProtocolTemplate(
            name="Migrated Protocol",
            content="Step 1",
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

        export = models.ExecutionNarrativeExport(
            execution_id=execution.id,
            version=1,
            format="markdown",
            content="legacy",
            event_count=0,
            generated_at=datetime.now(timezone.utc),
            requested_by_id=user_id,
            approval_status="pending",
            workflow_template_id=template_uuid,
        )
        export.meta = {}
        db.add(export)
        db.commit()
        export_id = export.id
    finally:
        db.close()

    summary = migrate_exports(dry_run=False)
    assert summary["dry_run"] is False

    db = TestingSessionLocal()
    try:
        migrated = db.get(models.ExecutionNarrativeExport, export_id)
        assert migrated.workflow_template_snapshot_id == uuid.UUID(snapshot_id)
        assert migrated.workflow_template_snapshot["template_id"] == template_id
        assert migrated.workflow_template_version == 1
    finally:
        db.close()


def test_preview_endpoint_generates_stage_insights(client):
    headers, user_id = admin_headers()

    template_payload = {
        "template_key": "preview-check",
        "name": "Preview Template",
        "description": "Preview validation",
        "default_stage_sla_hours": 24,
        "permitted_roles": ["scientist"],
        "stage_blueprint": [
            {
                "name": "Scientist Approval",
                "required_role": "scientist",
                "sla_hours": 24,
            }
        ],
        "publish": True,
    }
    template_resp = client.post("/api/governance/templates", json=template_payload, headers=headers)
    assert template_resp.status_code == 201
    template_data = template_resp.json()
    snapshot_id = uuid.UUID(template_data["published_snapshot_id"])

    db = TestingSessionLocal()
    try:
        protocol_template = models.ProtocolTemplate(
            name="Preview Protocol",
            content="Step 1\nStep 2",
            created_by=user_id,
        )
        db.add(protocol_template)
        db.flush()

        execution = models.ProtocolExecution(
            template_id=protocol_template.id,
            run_by=user_id,
            status="pending",
            params={},
            result={},
        )
        db.add(execution)
        db.commit()
        execution_id = execution.id
    finally:
        db.close()

    preview_payload = {
        "workflow_template_snapshot_id": str(snapshot_id),
        "stage_overrides": [{"index": 0, "sla_hours": 48}],
    }
    resp = client.post(
        f"/api/experiments/{execution_id}/preview",
        json=preview_payload,
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["snapshot_id"] == str(snapshot_id)
    assert body["stage_insights"]
    assert body["stage_insights"][0]["sla_hours"] == 48
    assert body["narrative_preview"].startswith("# Governance Preview")

    db = TestingSessionLocal()
    try:
        audit_entries = (
            db.query(models.GovernanceTemplateAuditLog)
            .filter(models.GovernanceTemplateAuditLog.snapshot_id == snapshot_id)
            .order_by(models.GovernanceTemplateAuditLog.created_at.desc())
            .all()
        )
        assert audit_entries
        assert any(entry.action == "template.preview.generated" for entry in audit_entries)
    finally:
        db.close()


def test_migrate_exports_dry_run_preserves_snapshot_binding():
    session = TestingSessionLocal()
    try:
        now = datetime.now(timezone.utc)
        user = models.User(
            email=f"cli-dry-run-{uuid.uuid4()}@example.com",
            hashed_password="placeholder",
        )
        session.add(user)
        session.flush()

        template = models.ExecutionNarrativeWorkflowTemplate(
            template_key="dry-run-migration",
            name="Dry Run Migration",
            description="Validate dry-run semantics",
            version=1,
            stage_blueprint=[{"name": "QA", "required_role": "qa"}],
            default_stage_sla_hours=24,
            permitted_roles=["qa"],
            status="published",
            created_by_id=user.id,
            published_at=now,
        )
        session.add(template)
        session.flush()

        protocol_template = models.ProtocolTemplate(
            name="Execution Template",
            content="Step 1",
            version="1",
            created_by=user.id,
        )
        session.add(protocol_template)
        session.flush()

        execution = models.ProtocolExecution(
            template_id=protocol_template.id,
            run_by=user.id,
            status="completed",
        )
        session.add(execution)
        session.flush()

        snapshot = models.ExecutionNarrativeWorkflowTemplateSnapshot(
            template_id=template.id,
            template_key=template.template_key,
            version=template.version,
            status="published",
            captured_by_id=user.id,
        )
        snapshot.snapshot_payload = {"template_id": str(template.id), "version": template.version}
        session.add(snapshot)
        session.flush()

        export = models.ExecutionNarrativeExport(
            execution_id=execution.id,
            requested_by_id=user.id,
            content="# Narrative\n",
            event_count=0,
            generated_at=now,
            approval_stage_count=1,
            workflow_template_id=template.id,
        )
        export.meta = {}
        session.add(export)
        session.commit()
        export_id = export.id
        snapshot_id = snapshot.id
        template_id = template.id
    finally:
        session.close()

    dry_summary = migrate_exports(dry_run=True)
    assert dry_summary["dry_run"] is True
    assert dry_summary["updated"] >= 1

    session = TestingSessionLocal()
    try:
        untouched = session.get(models.ExecutionNarrativeExport, export_id)
        assert untouched is not None
        assert untouched.workflow_template_snapshot_id is None
        assert untouched.workflow_template_snapshot == {}
    finally:
        session.close()

    commit_summary = migrate_exports(dry_run=False)
    assert commit_summary["dry_run"] is False

    session = TestingSessionLocal()
    try:
        refreshed = session.get(models.ExecutionNarrativeExport, export_id)
        assert refreshed is not None
        assert refreshed.workflow_template_snapshot_id == snapshot_id
        assert refreshed.workflow_template_key == "dry-run-migration"
        assert refreshed.workflow_template_version == 1
        assert refreshed.workflow_template_snapshot["template_id"] == str(template_id)
    finally:
        session.close()

def test_preview_requires_published_snapshot(client):
    headers, user_id = admin_headers()

    template_payload = {
        "template_key": "preview-status",
        "name": "Preview Status",
        "description": "Snapshot status validation",
        "default_stage_sla_hours": 12,
        "permitted_roles": ["qa"],
        "stage_blueprint": [
            {
                "name": "QA",
                "required_role": "qa",
                "sla_hours": 12,
            }
        ],
        "publish": True,
    }
    template_resp = client.post("/api/governance/templates", json=template_payload, headers=headers)
    template_data = template_resp.json()
    snapshot_id = uuid.UUID(template_data["published_snapshot_id"])

    db = TestingSessionLocal()
    try:
        snapshot = db.get(models.ExecutionNarrativeWorkflowTemplateSnapshot, snapshot_id)
        snapshot.status = "draft"
        protocol_template = models.ProtocolTemplate(
            name="Status Protocol",
            content="Step 1",
            created_by=user_id,
        )
        db.add(protocol_template)
        db.flush()
        execution = models.ProtocolExecution(
            template_id=protocol_template.id,
            run_by=user_id,
            status="pending",
            params={},
            result={},
        )
        db.add(execution)
        db.commit()
        execution_id = execution.id
    finally:
        db.close()

    resp = client.post(
        f"/api/experiments/{execution_id}/preview",
        json={"workflow_template_snapshot_id": str(snapshot_id)},
        headers=headers,
    )
    assert resp.status_code == 400
