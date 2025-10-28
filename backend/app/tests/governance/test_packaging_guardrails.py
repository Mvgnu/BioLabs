from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from app import models, schemas
from app.services import approval_ladders
from app.tasks import monitor_narrative_approval_slas
from app.workers.packaging import package_execution_narrative_export
from ..conftest import TestingSessionLocal


def _create_export_fixture(*, due_offset_minutes: int) -> UUID:
    session = TestingSessionLocal()
    try:
        now = datetime.now(timezone.utc)
        user = models.User(
            email=f"governance-tester-{uuid4()}@example.com",
            hashed_password="placeholder",
        )
        session.add(user)
        session.flush()

        template = models.ProtocolTemplate(
            name="Governance Ladder",
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
            content="# Narrative\n",
            event_count=0,
            generated_at=now,
            approval_stage_count=1,
            approval_status="in_progress",
        )
        export.requested_by = user
        session.add(export)
        session.flush()

        definition = schemas.ExecutionNarrativeApprovalStageDefinition(
            required_role="quality",
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
        session.flush()

        stage = export.approval_stages[0]
        stage.status = "in_progress"
        stage.started_at = now - timedelta(minutes=90)
        stage.due_at = now + timedelta(minutes=due_offset_minutes)
        stage.overdue_notified_at = None
        export.current_stage = stage
        export.current_stage_id = stage.id
        session.add(stage)
        session.add(export)
        session.commit()
        return export.id
    finally:
        session.close()


def test_verify_export_packaging_guardrails_blocks_unapproved_stage():
    export_id = _create_export_fixture(due_offset_minutes=60)

    session = TestingSessionLocal()
    try:
        tracked = session.get(models.ExecutionNarrativeExport, export_id)
        assert tracked is not None
        ready = approval_ladders.verify_export_packaging_guardrails(
            session, export=tracked
        )
        session.commit()
        assert ready is False

        events = (
            session.query(models.ExecutionEvent)
            .filter(models.ExecutionEvent.execution_id == tracked.execution_id)
            .filter(
                models.ExecutionEvent.event_type
                == "narrative_export.packaging.awaiting_approval"
            )
            .all()
        )
        assert events, "expected awaiting approval telemetry when guardrails block"

        stage = tracked.approval_stages[0]
        stage.status = "completed"
        stage.completed_at = datetime.now(timezone.utc)
        tracked.approval_status = "approved"
        tracked.current_stage = None
        tracked.current_stage_id = None
        session.add(stage)
        session.add(tracked)
        session.commit()

        refreshed = session.get(models.ExecutionNarrativeExport, export_id)
        assert refreshed is not None
        ready_again = approval_ladders.verify_export_packaging_guardrails(
            session, export=refreshed
        )
        assert ready_again is True
    finally:
        session.close()


def test_packaging_worker_rechecks_guardrails_before_processing():
    export_id = _create_export_fixture(due_offset_minutes=-30)

    result = package_execution_narrative_export.run(str(export_id))
    assert result == "pending_approval"

    session = TestingSessionLocal()
    try:
        tracked = session.get(models.ExecutionNarrativeExport, export_id)
        assert tracked is not None
        events = (
            session.query(models.ExecutionEvent)
            .filter(models.ExecutionEvent.execution_id == tracked.execution_id)
            .filter(
                models.ExecutionEvent.event_type
                == "narrative_export.packaging.awaiting_approval"
            )
            .all()
        )
        assert events, "worker should emit awaiting approval telemetry when ladder blocks"
    finally:
        session.close()


def test_sla_monitor_revalidates_guardrails():
    export_id = _create_export_fixture(due_offset_minutes=-15)

    monitor_narrative_approval_slas.run()

    session = TestingSessionLocal()
    try:
        tracked = session.get(models.ExecutionNarrativeExport, export_id)
        assert tracked is not None
        stage = tracked.approval_stages[0]
        assert stage.overdue_notified_at is not None
        events = (
            session.query(models.ExecutionEvent)
            .filter(models.ExecutionEvent.execution_id == tracked.execution_id)
            .filter(
                models.ExecutionEvent.event_type
                == "narrative_export.packaging.awaiting_approval"
            )
            .all()
        )
        assert events, "SLA monitor should reissue guardrail telemetry for overdue stages"
    finally:
        session.close()
