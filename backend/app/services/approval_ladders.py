"""Service helpers orchestrating execution narrative approval ladders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Iterable, Mapping, Sequence
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..analytics.governance import invalidate_governance_analytics_cache
from ..eventlog import record_execution_event

# purpose: centralise execution narrative ladder orchestration for reuse across APIs and workers
# status: pilot
# related_docs: backend/app/README.md


@dataclass(slots=True)
class StageActionResult:
    """Outcome of a stage action including packaging trigger metadata."""

    # purpose: carry approval ladder transition data for downstream handlers
    # inputs: approval ladder stage transition operations
    # outputs: export state plus packaging trigger indicator for workers
    # status: pilot
    export: models.ExecutionNarrativeExport
    should_queue_packaging: bool = False


def _serialise_guardrail_record(
    record: models.GovernanceGuardrailSimulation,
) -> schemas.GovernanceGuardrailSimulationRecord:
    summary_payload = record.summary or {}
    summary = schemas.GovernanceGuardrailSummary(
        state=summary_payload.get("state", record.state or "clear"),
        reasons=list(summary_payload.get("reasons", [])),
        regressed_stage_indexes=list(summary_payload.get("regressed_stage_indexes", [])),
        projected_delay_minutes=int(summary_payload.get("projected_delay_minutes", 0)),
    )
    actor = record.actor
    actor_schema = schemas.UserOut.model_validate(actor) if actor is not None else None
    metadata = (record.payload or {}).get("metadata", {})
    return schemas.GovernanceGuardrailSimulationRecord(
        id=record.id,
        execution_id=record.execution_id,
        actor=actor_schema,
        summary=summary,
        metadata=metadata,
        created_at=record.created_at,
        state=record.state,
        projected_delay_minutes=record.projected_delay_minutes,
    )


def load_guardrail_simulations(
    db: Session,
    *,
    execution_id: UUID,
    limit: int = 10,
) -> list[schemas.GovernanceGuardrailSimulationRecord]:
    """Return persisted guardrail simulations for an execution."""

    # purpose: fetch ordered guardrail simulations for export annotation
    # inputs: SQLAlchemy session, execution identifier, optional limit
    # outputs: list of serialised guardrail simulation records
    # status: pilot
    query = (
        db.query(models.GovernanceGuardrailSimulation)
        .options(joinedload(models.GovernanceGuardrailSimulation.actor))
        .filter(models.GovernanceGuardrailSimulation.execution_id == execution_id)
        .order_by(models.GovernanceGuardrailSimulation.created_at.desc())
    )
    if limit is not None and limit > 0:
        query = query.limit(limit)
    return [_serialise_guardrail_record(record) for record in query.all()]


def attach_guardrail_forecast(
    db: Session, export: models.ExecutionNarrativeExport
) -> schemas.GovernanceGuardrailSimulationRecord | None:
    """Annotate export with the latest guardrail forecast snapshot for its execution."""

    # purpose: decorate exports with guardrail simulation summaries for UI consumers
    # inputs: SQLAlchemy session and export record
    # outputs: mutates export with guardrail_simulation attribute when forecast exists
    # status: pilot
    forecast = (
        db.query(models.GovernanceGuardrailSimulation)
        .options(joinedload(models.GovernanceGuardrailSimulation.actor))
        .filter(models.GovernanceGuardrailSimulation.execution_id == export.execution_id)
        .order_by(models.GovernanceGuardrailSimulation.created_at.desc())
        .first()
    )
    if forecast is None:
        export.guardrail_simulation = None
        return None
    record = _serialise_guardrail_record(forecast)
    export.guardrail_simulation = record
    return record


def attach_guardrail_history(
    db: Session,
    export: models.ExecutionNarrativeExport,
    *,
    limit: int = 10,
) -> list[schemas.GovernanceGuardrailSimulationRecord]:
    """Attach recent guardrail simulations to an export instance."""

    # purpose: decorate exports with guardrail simulation history for governance surfaces
    # inputs: db session, export ORM model, optional limit for history size
    # outputs: list of guardrail simulation records assigned to export.guardrail_simulations
    # status: pilot
    history = (
        load_guardrail_simulations(
            db,
            execution_id=export.execution_id,
            limit=limit,
        )
        if export.execution_id is not None
        else []
    )
    export.guardrail_simulations = history
    return history


def load_export_with_ladder(
    db: Session,
    *,
    export_id: UUID,
    execution_id: UUID | None = None,
    include_attachments: bool = False,
    include_guardrails: bool = False,
) -> models.ExecutionNarrativeExport:
    """Return an export with approval ladder relationships eager loaded."""

    query = (
        db.query(models.ExecutionNarrativeExport)
        .options(
            joinedload(models.ExecutionNarrativeExport.requested_by),
            joinedload(models.ExecutionNarrativeExport.approved_by),
            joinedload(models.ExecutionNarrativeExport.artifact_file),
            joinedload(models.ExecutionNarrativeExport.execution),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.actions)
            .joinedload(models.ExecutionNarrativeApprovalAction.actor),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.actions)
            .joinedload(models.ExecutionNarrativeApprovalAction.delegation_target),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.assignee),
            joinedload(models.ExecutionNarrativeExport.approval_stages)
            .joinedload(models.ExecutionNarrativeApprovalStage.delegated_to),
        )
        .filter(models.ExecutionNarrativeExport.id == export_id)
        )
    if execution_id:
        query = query.filter(models.ExecutionNarrativeExport.execution_id == execution_id)
    if include_attachments:
        query = query.options(
            joinedload(models.ExecutionNarrativeExport.attachments).joinedload(
                models.ExecutionNarrativeExportAttachment.file
            )
        )
    export = query.first()
    if not export:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Narrative export not found")
    if include_guardrails:
        attach_guardrail_forecast(db, export)
        attach_guardrail_history(db, export)
    else:
        export.guardrail_simulations = []
    return export


def initialise_export_ladder(
    export: models.ExecutionNarrativeExport,
    stage_definitions: Sequence[schemas.ExecutionNarrativeApprovalStageDefinition],
    resolved_users: Mapping[UUID, models.User],
    *,
    now: datetime,
) -> None:
    """Populate the export approval ladder using supplied stage definitions."""

    definitions = list(stage_definitions)
    if not definitions:
        definitions = [schemas.ExecutionNarrativeApprovalStageDefinition(required_role="approver")]

    export.approval_stages[:] = []
    export.approval_stage_count = len(definitions)
    export.current_stage = None
    export.current_stage_started_at = None

    for index, stage_def in enumerate(definitions, start=1):
        status_value = "in_progress" if index == 1 else "pending"
        started_at = now if status_value == "in_progress" else None
        due_at = None
        if stage_def.sla_hours and status_value == "in_progress":
            due_at = now + timedelta(hours=stage_def.sla_hours)
        stage = models.ExecutionNarrativeApprovalStage(
            sequence_index=index,
            name=stage_def.name,
            required_role=stage_def.required_role,
            status=status_value,
            sla_hours=stage_def.sla_hours,
            started_at=started_at,
            due_at=due_at,
            assignee_id=stage_def.assignee_id,
            delegated_to_id=stage_def.delegate_id,
        )
        stage.meta = stage_def.metadata or {}
        if stage.assignee_id and stage.assignee_id in resolved_users:
            stage.assignee = resolved_users[stage.assignee_id]
        if stage.delegated_to_id and stage.delegated_to_id in resolved_users:
            stage.delegated_to = resolved_users[stage.delegated_to_id]
        export.approval_stages.append(stage)

    if export.approval_stages:
        export.current_stage = export.approval_stages[0]
        export.current_stage_started_at = now


def _ordered_stages(
    export: models.ExecutionNarrativeExport,
) -> list[models.ExecutionNarrativeApprovalStage]:
    return sorted(export.approval_stages, key=lambda item: item.sequence_index)


def record_packaging_queue_state(
    db: Session,
    *,
    export: models.ExecutionNarrativeExport,
    actor: models.User | None = None,
) -> bool:
    """Emit packaging queue state events and signal when dispatch is allowed."""

    # purpose: centralise packaging gating semantics for exports across API surfaces
    # inputs: db session, export with ladder relationships, optional actor for audit trail
    # outputs: bool indicating whether packaging may be enqueued immediately
    # status: pilot
    meta_payload: dict[str, Any] = dict(export.meta or {})
    previous_state: dict[str, Any] = {}
    if isinstance(meta_payload.get("packaging_queue_state"), dict):
        previous_state = dict(meta_payload["packaging_queue_state"])

    def _emit(event_type: str, state_payload: dict[str, Any]) -> None:
        nonlocal previous_state, meta_payload
        if export.execution is None:
            return
        next_state = {"event": event_type, **state_payload}
        if previous_state == next_state:
            return
        record_execution_event(
            db,
            export.execution,
            event_type,
            {"export_id": str(export.id), **state_payload},
            actor=actor,
        )
        previous_state = next_state
        meta_payload["packaging_queue_state"] = next_state
        export.meta = meta_payload

    guardrail = getattr(export, "guardrail_simulation", None)
    if guardrail is None:
        guardrail = attach_guardrail_forecast(db, export)
    if guardrail and guardrail.summary.state == "blocked":
        payload: dict[str, Any] = {
            "state": "guardrail_blocked",
            "guardrail_state": guardrail.summary.state,
        }
        if guardrail.summary.projected_delay_minutes is not None:
            payload["projected_delay_minutes"] = guardrail.summary.projected_delay_minutes
        if guardrail.summary.reasons:
            payload["reasons"] = guardrail.summary.reasons
        _emit("narrative_export.packaging.guardrail_blocked", payload)
        return False
    if export.approval_status == "approved" and export.current_stage is None:
        payload = {
            "state": "queued",
            "version": export.version,
            "event_count": export.event_count,
        }
        _emit("narrative_export.packaging.queued", payload)
        return True

    pending_stage = export.current_stage
    if pending_stage is None:
        for stage in _ordered_stages(export):
            if stage.status in {"in_progress", "pending", "delegated"}:
                pending_stage = stage
                break

    payload = {
        "state": "awaiting_approval",
        "pending_stage_id": str(pending_stage.id) if pending_stage else None,
        "pending_stage_index": pending_stage.sequence_index if pending_stage else None,
        "pending_stage_status": pending_stage.status if pending_stage else None,
    }
    if pending_stage and pending_stage.due_at:
        payload["pending_stage_due_at"] = pending_stage.due_at.isoformat()
    _emit("narrative_export.packaging.awaiting_approval", payload)

    return False


def dispatch_export_for_packaging(
    db: Session,
    *,
    export: models.ExecutionNarrativeExport,
    actor: models.User | None = None,
    enqueue: Callable[[UUID | str], None] | None = None,
) -> bool:
    """Apply guardrail and ladder gating before enqueuing packaging."""

    # purpose: guarantee narrative packaging dispatch respects shared enforcement
    # inputs: db session, export ORM instance, optional actor context, optional enqueue hook
    # outputs: bool indicating whether packaging was queued
    # status: pilot
    should_queue = record_packaging_queue_state(db, export=export, actor=actor)
    db.flush()
    if not should_queue:
        return False

    if enqueue is None:
        from ..workers.packaging import enqueue_narrative_export_packaging as enqueue_fn
    else:
        enqueue_fn = enqueue

    enqueue_fn(export.id)
    return True


def verify_export_packaging_guardrails(
    db: Session,
    *,
    export: models.ExecutionNarrativeExport,
    actor: models.User | None = None,
) -> bool:
    """Re-evaluate ladder readiness before performing packaging side effects."""

    # purpose: guard Celery workers and schedulers from processing unapproved exports
    # inputs: db session, export ORM instance, optional actor context for telemetry
    # outputs: bool signalling whether packaging side effects may proceed
    # status: pilot
    ready = export.approval_status == "approved" and export.current_stage is None
    if ready:
        meta_payload: dict[str, Any] = dict(export.meta or {})
        meta_payload["packaging_queue_state"] = {
            "event": "narrative_export.packaging.ready",
            "state": "ready",
        }
        export.meta = meta_payload
        return True

    record_packaging_queue_state(db, export=export, actor=actor)
    db.flush()
    return False


def dispatch_export_for_packaging_by_id(
    db: Session,
    *,
    export_id: UUID,
    actor: models.User | None = None,
    enqueue: Callable[[UUID | str], None] | None = None,
    include_guardrails: bool = True,
) -> bool:
    """Load an export and route it through shared packaging dispatch checks."""

    # purpose: reuse dispatch semantics for CLI, schedulers, and background tasks
    # inputs: db session, export identifier, optional actor context and enqueue hook
    # outputs: bool indicating whether packaging was queued after gating
    # status: pilot
    export = load_export_with_ladder(
        db,
        export_id=export_id,
        include_guardrails=include_guardrails,
    )
    return dispatch_export_for_packaging(
        db,
        export=export,
        actor=actor,
        enqueue=enqueue,
    )


def _resolve_active_stage(
    export: models.ExecutionNarrativeExport,
    stage_id: UUID | None,
) -> models.ExecutionNarrativeApprovalStage:
    stage_lookup = {stage.id: stage for stage in _ordered_stages(export)}
    active_stage_id = stage_id or export.current_stage_id
    if not active_stage_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No active approval stage available")
    stage = stage_lookup.get(UUID(str(active_stage_id)))
    if not stage:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval stage not found")
    if stage.status != "in_progress":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Approval stage is not active")
    return stage


def _resolve_next_stage(
    export: models.ExecutionNarrativeExport,
    current: models.ExecutionNarrativeApprovalStage,
) -> models.ExecutionNarrativeApprovalStage | None:
    for candidate in _ordered_stages(export):
        if candidate.sequence_index > current.sequence_index:
            return candidate
    return None


def _ensure_actor_authorized(
    *,
    stage: models.ExecutionNarrativeApprovalStage,
    acting_user: models.User,
    approver: models.User,
) -> None:
    allowed_actor_ids = {
        value
        for value in (stage.assignee_id, stage.delegated_to_id)
        if value is not None
    }
    if allowed_actor_ids and approver.id not in allowed_actor_ids and not acting_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User not authorized for this stage")


def _resolve_approver(
    db: Session,
    *,
    approval: schemas.ExecutionNarrativeApprovalRequest,
    acting_user: models.User,
) -> models.User:
    if approval.approver_id and approval.approver_id != acting_user.id:
        approver = db.query(models.User).filter(models.User.id == approval.approver_id).first()
        if not approver:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approver not found")
        if not acting_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only administrators may sign on behalf of another user",
            )
        return approver
    return acting_user


def record_stage_decision(
    db: Session,
    *,
    export: models.ExecutionNarrativeExport,
    approval: schemas.ExecutionNarrativeApprovalRequest,
    acting_user: models.User,
    now: datetime | None = None,
) -> StageActionResult:
    """Persist approval or rejection for an active stage."""

    timestamp = now or datetime.now(timezone.utc)
    stage = _resolve_active_stage(export, approval.stage_id)
    approver = _resolve_approver(db, approval=approval, acting_user=acting_user)
    _ensure_actor_authorized(stage=stage, acting_user=acting_user, approver=approver)

    stage.status = "approved" if approval.status == "approved" else "rejected"
    stage.completed_at = timestamp
    if approval.notes:
        stage.notes = approval.notes

    action = models.ExecutionNarrativeApprovalAction(
        actor_id=approver.id,
        action_type=approval.status,
        signature=approval.signature,
        notes=approval.notes,
    )
    action.meta = approval.metadata or {}
    stage.actions.append(action)

    export.approval_signature = approval.signature

    next_stage = _resolve_next_stage(export, stage)
    should_queue_packaging = False

    if approval.status == "approved" and next_stage:
        next_stage.status = "in_progress"
        next_stage.started_at = timestamp
        if next_stage.sla_hours:
            next_stage.due_at = timestamp + timedelta(hours=next_stage.sla_hours)
        export.current_stage = next_stage
        export.current_stage_started_at = timestamp
        export.approval_status = "pending"
    elif approval.status == "approved":
        export.current_stage = None
        export.current_stage_started_at = None
        export.approval_status = "approved"
        export.approved_by_id = approver.id
        export.approved_by = approver
        export.approved_at = timestamp
        export.approval_completed_at = timestamp
        should_queue_packaging = True
    else:
        export.current_stage = None
        export.current_stage_started_at = None
        export.approval_status = "rejected"
        export.approved_by_id = approver.id
        export.approved_by = approver
        export.approved_at = timestamp
        export.approval_completed_at = timestamp
        for candidate in export.approval_stages:
            if candidate.sequence_index > stage.sequence_index:
                candidate.status = "reset"
                candidate.started_at = None
                candidate.due_at = None

    record_execution_event(
        db,
        export.execution,
        "narrative_export.approval.stage_completed",
        {
            "export_id": str(export.id),
            "stage_id": str(stage.id),
            "sequence_index": stage.sequence_index,
            "status": stage.status,
            "signature": approval.signature,
            "actor_id": str(approver.id),
        },
        actor=acting_user,
    )
    db.flush()

    if next_stage and approval.status == "approved":
        record_execution_event(
            db,
            export.execution,
            "narrative_export.approval.stage_started",
            {
                "export_id": str(export.id),
                "stage_id": str(next_stage.id),
                "sequence_index": next_stage.sequence_index,
                "required_role": next_stage.required_role,
                "assignee_id": str(next_stage.assignee_id) if next_stage.assignee_id else None,
                "due_at": next_stage.due_at.isoformat() if next_stage.due_at else None,
            },
            actor=acting_user,
        )
        db.flush()

    if not next_stage and approval.status == "approved":
        record_execution_event(
            db,
            export.execution,
            "narrative_export.approval.finalized",
            {
                "export_id": str(export.id),
                "approved_at": timestamp.isoformat(),
                "approver_id": str(approver.id),
                "status": "approved",
            },
            actor=acting_user,
        )
        db.flush()

    if approval.status == "rejected":
        record_execution_event(
            db,
            export.execution,
            "narrative_export.approval.rejected",
            {
                "export_id": str(export.id),
                "stage_id": str(stage.id),
                "sequence_index": stage.sequence_index,
                "actor_id": str(approver.id),
            },
            actor=acting_user,
        )
        db.flush()

    invalidate_governance_analytics_cache(execution_ids=[export.execution_id])
    return StageActionResult(export=export, should_queue_packaging=should_queue_packaging)


def delegate_stage(
    db: Session,
    *,
    export: models.ExecutionNarrativeExport,
    stage_id: UUID,
    payload: schemas.ExecutionNarrativeApprovalDelegationRequest,
    acting_user: models.User,
    now: datetime | None = None,
) -> models.ExecutionNarrativeExport:
    """Assign a delegate for the supplied stage."""

    timestamp = now or datetime.now(timezone.utc)
    stage_lookup = {stage.id: stage for stage in _ordered_stages(export)}
    stage = stage_lookup.get(stage_id)
    if not stage:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval stage not found")
    if stage.status not in {"pending", "in_progress", "delegated"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Stage cannot be delegated")

    delegate = db.query(models.User).filter(models.User.id == payload.delegate_id).first()
    if not delegate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delegate not found")

    stage.delegated_to_id = delegate.id
    stage.delegated_to = delegate
    stage.status = "delegated" if stage.status != "in_progress" else stage.status

    action = models.ExecutionNarrativeApprovalAction(
        actor_id=acting_user.id,
        action_type="delegated",
        notes=payload.notes,
        delegation_target_id=delegate.id,
    )
    stage.actions.append(action)

    record_execution_event(
        db,
        export.execution,
        "narrative_export.approval.stage_delegated",
        {
            "export_id": str(export.id),
            "stage_id": str(stage.id),
            "sequence_index": stage.sequence_index,
            "delegate_id": str(delegate.id),
            "notes": payload.notes,
        },
        actor=acting_user,
    )
    db.flush()

    invalidate_governance_analytics_cache(execution_ids=[export.execution_id])
    return export


def reset_stage(
    db: Session,
    *,
    export: models.ExecutionNarrativeExport,
    stage_id: UUID,
    payload: schemas.ExecutionNarrativeApprovalResetRequest,
    acting_user: models.User,
    now: datetime | None = None,
) -> models.ExecutionNarrativeExport:
    """Reset a stage back to in-progress status for remediation."""

    timestamp = now or datetime.now(timezone.utc)
    stage_lookup = {stage.id: stage for stage in _ordered_stages(export)}
    stage = stage_lookup.get(stage_id)
    if not stage:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval stage not found")

    stage.status = "in_progress"
    stage.started_at = timestamp
    if stage.sla_hours:
        stage.due_at = timestamp + timedelta(hours=stage.sla_hours)
    stage.notes = payload.notes or stage.notes

    action = models.ExecutionNarrativeApprovalAction(
        actor_id=acting_user.id,
        action_type="reset",
        notes=payload.notes,
    )
    stage.actions.append(action)

    export.current_stage = stage
    export.current_stage_started_at = timestamp
    export.approval_status = "pending"
    export.approved_by = None
    export.approved_by_id = None
    export.approved_at = None
    export.approval_completed_at = None

    for candidate in export.approval_stages:
        if candidate.sequence_index > stage.sequence_index:
            candidate.status = "pending"
            candidate.started_at = None
            candidate.due_at = None

    record_execution_event(
        db,
        export.execution,
        "narrative_export.approval.stage_reset",
        {
            "export_id": str(export.id),
            "stage_id": str(stage.id),
            "sequence_index": stage.sequence_index,
            "notes": payload.notes,
        },
        actor=acting_user,
    )
    db.flush()

    invalidate_governance_analytics_cache(execution_ids=[export.execution_id])
    return export


