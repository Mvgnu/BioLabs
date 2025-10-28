from datetime import datetime, timezone
from uuid import UUID, uuid4

from app import models, schemas
from app.cli.migrate_templates import queue_narrative_export
from app.services import approval_ladders
from .conftest import TestingSessionLocal


def _build_export_fixture(session: TestingSessionLocal) -> UUID:
    now = datetime.now(timezone.utc)
    user = models.User(email=f"cli-tester-{uuid4()}@example.com", hashed_password="placeholder")
    session.add(user)
    session.flush()

    template = models.ProtocolTemplate(
        name="CLI Governance Template",
        content="Stage 1",
        version="1",
        created_by=user.id,
    )
    session.add(template)
    session.flush()

    execution = models.ProtocolExecution(
        template_id=template.id,
        run_by=user.id,
        status="in_progress",
    )
    session.add(execution)
    session.flush()

    export = models.ExecutionNarrativeExport(
        execution_id=execution.id,
        requested_by_id=user.id,
        content="# Narrative\n",  # minimal payload for packaging
        event_count=0,
        generated_at=now,
        approval_stage_count=1,
    )
    export.requested_by = user
    session.add(export)
    session.flush()

    definition = schemas.ExecutionNarrativeApprovalStageDefinition(
        required_role="approver",
        name="QA",
        assignee_id=user.id,
        sla_hours=1,
    )
    approval_ladders.initialise_export_ladder(
        export,
        [definition],
        resolved_users={user.id: user},
        now=now,
    )
    session.add(export)
    session.commit()
    return export.id


def test_queue_narrative_export_blocks_until_stage_completed(monkeypatch):
    enqueued: list[str] = []
    monkeypatch.setattr(
        "app.cli.migrate_templates.enqueue_narrative_export_packaging",
        lambda export_id: enqueued.append(str(export_id)),
    )
    session = TestingSessionLocal()
    try:
        export_id = _build_export_fixture(session)
    finally:
        session.close()

    first_summary = queue_narrative_export(export_id)
    assert first_summary["queued"] is False
    assert first_summary["pending_stage_status"] in {"in_progress", "delegated", "pending"}

    session = TestingSessionLocal()
    try:
        export = session.get(models.ExecutionNarrativeExport, export_id)
        assert export is not None
        stage = export.approval_stages[0]
        stage.status = "completed"
        stage.completed_at = datetime.now(timezone.utc)
        export.approval_status = "approved"
        export.current_stage = None
        export.current_stage_id = None
        session.add(stage)
        session.add(export)
        session.commit()
    finally:
        session.close()

    second_summary = queue_narrative_export(export_id)
    assert second_summary["queued"] is True
    assert enqueued == [str(export_id)]

    session = TestingSessionLocal()
    try:
        refreshed = session.get(models.ExecutionNarrativeExport, export_id)
        assert refreshed is not None
        assert refreshed.artifact_status in {"processing", "ready", "retrying", "queued"}
    finally:
        session.close()
