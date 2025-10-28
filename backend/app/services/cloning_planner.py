"""Cloning planner orchestration helpers."""

# purpose: provide shared workflow management for multi-stage cloning planner sessions
# status: experimental
# depends_on: backend.app.models, backend.app.schemas

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from .. import models


def _utcnow() -> datetime:
    """Return timezone-aware utc timestamp."""

    # purpose: standardize timezone-aware timestamps for planner persistence
    # outputs: datetime in UTC
    # status: experimental
    return datetime.now(timezone.utc)


def create_session(
    db: Session,
    *,
    created_by: models.User | None,
    assembly_strategy: str,
    input_sequences: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> models.CloningPlannerSession:
    """Initialise a cloning planner session with intake context."""

    # purpose: seed resumable planner session rows prior to background orchestration
    # inputs: db session, optional creator, assembly strategy choice, optional sequences and metadata
    # outputs: persisted CloningPlannerSession ORM instance
    # status: experimental
    now = _utcnow()
    record = models.CloningPlannerSession(
        created_by_id=getattr(created_by, "id", None),
        assembly_strategy=assembly_strategy,
        input_sequences=list(input_sequences or []),
        guardrail_state=dict(metadata.get("guardrail_state", {})) if metadata else {},
        stage_timings={"intake": now.isoformat()},
        current_step="intake",
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    db.flush()
    db.refresh(record)
    return record


def record_stage_progress(
    db: Session,
    *,
    planner: models.CloningPlannerSession,
    step: str,
    payload: dict[str, Any],
    next_step: str | None = None,
    status: str | None = None,
    guardrail_state: dict[str, Any] | None = None,
    task_id: str | None = None,
    error: str | None = None,
) -> models.CloningPlannerSession:
    """Persist outputs for a planner stage and advance state tracking."""

    # purpose: centralise stage persistence semantics across API surfaces and Celery tasks
    # inputs: db session, planner record, stage identifier, stage payload, optional status/guardrail/task details
    # outputs: updated CloningPlannerSession instance with refreshed metadata
    # status: experimental
    now = _utcnow()
    step_map = {
        "primers": "primer_set",
        "restriction": "restriction_digest",
        "assembly": "assembly_plan",
        "qc": "qc_reports",
    }
    target_field = step_map.get(step)
    if target_field is None and step != "intake":
        raise ValueError(f"Unsupported cloning planner step: {step}")

    if target_field:
        setattr(planner, target_field, payload)
    else:
        planner.input_sequences = payload if step == "intake" else planner.input_sequences

    if guardrail_state is not None:
        planner.guardrail_state = guardrail_state
    if task_id is not None:
        planner.celery_task_id = task_id
    planner.last_error = error
    planner.stage_timings = dict(planner.stage_timings or {})
    planner.stage_timings[step] = now.isoformat()
    planner.updated_at = now
    if next_step:
        planner.current_step = next_step
    if status:
        planner.status = status
        if status in {"finalized", "completed"}:
            planner.completed_at = now
    db.add(planner)
    db.flush()
    db.refresh(planner)
    return planner


def finalize_session(
    db: Session,
    *,
    planner: models.CloningPlannerSession,
    guardrail_state: dict[str, Any] | None = None,
) -> models.CloningPlannerSession:
    """Mark a planner session as finalized and capture guardrail context."""

    # purpose: conclude planner workflows once guardrails pass and outputs assembled
    # inputs: db session, planner record, optional guardrail payload for final state
    # outputs: finalized CloningPlannerSession instance
    # status: experimental
    now = _utcnow()
    if guardrail_state is not None:
        planner.guardrail_state = guardrail_state
    planner.status = "finalized"
    planner.current_step = "finalized"
    planner.completed_at = now
    planner.updated_at = now
    db.add(planner)
    db.flush()
    db.refresh(planner)
    return planner


def serialize_session(planner: models.CloningPlannerSession) -> dict[str, Any]:
    """Render a cloning planner session into a JSON-serialisable dict."""

    # purpose: provide consistent API responses for planner session payloads
    # inputs: CloningPlannerSession ORM instance
    # outputs: dictionary for JSON responses
    # status: experimental
    return {
        "id": planner.id,
        "created_by_id": planner.created_by_id,
        "status": planner.status,
        "assembly_strategy": planner.assembly_strategy,
        "input_sequences": planner.input_sequences,
        "primer_set": planner.primer_set,
        "restriction_digest": planner.restriction_digest,
        "assembly_plan": planner.assembly_plan,
        "qc_reports": planner.qc_reports,
        "inventory_reservations": planner.inventory_reservations,
        "guardrail_state": planner.guardrail_state,
        "stage_timings": planner.stage_timings,
        "current_step": planner.current_step,
        "celery_task_id": planner.celery_task_id,
        "last_error": planner.last_error,
        "created_at": planner.created_at,
        "updated_at": planner.updated_at,
        "completed_at": planner.completed_at,
    }
