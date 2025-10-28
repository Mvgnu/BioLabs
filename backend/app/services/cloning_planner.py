"""Cloning planner orchestration helpers."""

# purpose: provide shared workflow management for multi-stage cloning planner sessions
# status: experimental
# depends_on: backend.app.models, backend.app.schemas

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence
import json
from uuid import UUID

from sqlalchemy.orm import Session

from .. import models
from ..database import SessionLocal
from ..schemas.sequence_toolkit import SequenceToolkitProfile
from . import sequence_toolkit
from ..tasks import celery_app


DEFAULT_TOOLKIT_PROFILE = SequenceToolkitProfile()


def _merge_guardrail_state(
    planner: models.CloningPlannerSession, updates: dict[str, Any]
) -> dict[str, Any]:
    """Merge guardrail updates into the planner state."""

    # purpose: keep guardrail snapshots cumulative across orchestration stages
    base = dict(planner.guardrail_state or {})
    base.update(updates)
    return base


def _primer_guardrail_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Summarise primer design quality for guardrail tracking."""

    primers = [p for p in result.get("primers", []) if p.get("status") == "ok"]
    warning_count = sum(len(p.get("warnings", [])) for p in primers)
    return {
        "primer_sets": len(primers),
        "primer_warnings": warning_count,
        "primer_state": "review" if warning_count else "ok",
    }


def _restriction_guardrail_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Summarise restriction digest compatibility for guardrail tracking."""

    alerts = result.get("alerts", [])
    return {
        "restriction_alerts": alerts,
        "restriction_state": "review" if alerts else "ok",
    }


def _assembly_guardrail_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Summarise assembly simulation outcomes for guardrail tracking."""

    success = result.get("average_success", 0.0)
    state = "ok" if success >= 0.7 else "review"
    return {
        "assembly_success": success,
        "assembly_state": state,
    }


def _qc_guardrail_summary(result: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    """Summarise QC checkpoints for guardrail tracking."""

    if isinstance(result, dict):
        reports = result.get("reports", [])
    else:
        reports = result
    statuses = {entry.get("status") for entry in reports}
    state = "ok" if statuses <= {"pass"} else "review"
    return {
        "qc_state": state,
        "qc_checks": len(reports),
    }


def compose_guardrail_state(
    planner: models.CloningPlannerSession,
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an aggregated guardrail snapshot from planner outputs."""

    snapshot = dict(planner.guardrail_state or {})
    if planner.primer_set:
        snapshot["primers"] = _primer_guardrail_summary(planner.primer_set)
    if planner.restriction_digest:
        snapshot["restriction"] = _restriction_guardrail_summary(planner.restriction_digest)
    if planner.assembly_plan:
        snapshot["assembly"] = _assembly_guardrail_summary(planner.assembly_plan)
    if planner.qc_reports:
        snapshot["qc"] = _qc_guardrail_summary(planner.qc_reports)
    if override:
        snapshot.update(override)
    return snapshot


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


def run_primer_design(
    db: Session,
    *,
    planner: models.CloningPlannerSession,
    product_size_range: tuple[int, int] | None = None,
    target_tm: float | None = None,
) -> models.CloningPlannerSession:
    """Execute primer design stage for a planner session."""

    # purpose: derive primer sets via Primer3 for planner sequences
    # inputs: planner record and optional primer sizing overrides
    # outputs: updated planner with primer_set payload and guardrail summary
    # status: experimental
    profile = DEFAULT_TOOLKIT_PROFILE
    primer_payload = sequence_toolkit.design_primers(
        planner.input_sequences,
        config=profile,
        product_size_range=product_size_range or (80, 280),
        target_tm=target_tm or 60.0,
    )
    guardrail_state = _merge_guardrail_state(
        planner,
        {"primers": _primer_guardrail_summary(primer_payload)},
    )
    return record_stage_progress(
        db,
        planner=planner,
        step="primers",
        payload=primer_payload,
        next_step="restriction",
        status="primer_complete",
        guardrail_state=guardrail_state,
    )


def run_restriction_analysis(
    db: Session,
    *,
    planner: models.CloningPlannerSession,
    enzymes: Sequence[str] | None = None,
) -> models.CloningPlannerSession:
    """Execute restriction digest analysis for a planner session."""

    # purpose: score multi-enzyme compatibility for planner guardrails
    # inputs: planner record and optional enzyme overrides
    # outputs: updated planner with restriction digest payload
    # status: experimental
    profile = DEFAULT_TOOLKIT_PROFILE
    digest_payload = sequence_toolkit.analyze_restriction_digest(
        planner.input_sequences,
        config=profile,
        enzymes=enzymes,
    )
    guardrail_state = _merge_guardrail_state(
        planner,
        {"restriction": _restriction_guardrail_summary(digest_payload)},
    )
    return record_stage_progress(
        db,
        planner=planner,
        step="restriction",
        payload=digest_payload,
        next_step="assembly",
        status="restriction_complete",
        guardrail_state=guardrail_state,
    )


def run_assembly_planning(
    db: Session,
    *,
    planner: models.CloningPlannerSession,
    strategy: str | None = None,
) -> models.CloningPlannerSession:
    """Execute assembly simulation for a planner session."""

    # purpose: simulate assembly junction success probabilities
    # inputs: planner record and optional strategy override
    # outputs: updated planner with assembly plan payload
    # status: experimental
    profile = DEFAULT_TOOLKIT_PROFILE
    plan_payload = sequence_toolkit.simulate_assembly(
        planner.primer_set,
        planner.restriction_digest,
        config=profile,
        strategy=strategy or planner.assembly_strategy,
    )
    guardrail_state = _merge_guardrail_state(
        planner,
        {"assembly": _assembly_guardrail_summary(plan_payload)},
    )
    return record_stage_progress(
        db,
        planner=planner,
        step="assembly",
        payload=plan_payload,
        next_step="qc",
        status="assembly_complete",
        guardrail_state=guardrail_state,
    )


def run_qc_checks(
    db: Session,
    *,
    planner: models.CloningPlannerSession,
    chromatograms: Sequence[dict[str, Any]] | None = None,
) -> models.CloningPlannerSession:
    """Execute QC evaluation for a planner session."""

    # purpose: gate planner completion on QC checkpoints and chromatogram data
    # inputs: planner record with optional chromatogram descriptors
    # outputs: updated planner with qc payload and guardrail snapshot
    # status: experimental
    profile = DEFAULT_TOOLKIT_PROFILE
    qc_payload = sequence_toolkit.evaluate_qc_reports(
        planner.assembly_plan,
        config=profile,
        chromatograms=chromatograms,
    )
    guardrail_state = _merge_guardrail_state(
        planner,
        {"qc": _qc_guardrail_summary(qc_payload)},
    )
    return record_stage_progress(
        db,
        planner=planner,
        step="qc",
        payload=qc_payload,
        next_step="finalize",
        status="qc_complete",
        guardrail_state=guardrail_state,
    )


def run_full_pipeline(
    db: Session,
    planner: models.CloningPlannerSession,
    *,
    product_size_range: tuple[int, int] | None = None,
    target_tm: float | None = None,
    enzymes: Sequence[str] | None = None,
    chromatograms: Sequence[dict[str, Any]] | None = None,
) -> models.CloningPlannerSession:
    """Run primer, restriction, assembly, and QC stages sequentially."""

    # purpose: provide a synchronous orchestration helper for Celery pipelines
    # inputs: planner record with optional configuration overrides
    # outputs: planner record updated through qc stage
    # status: experimental
    planner = run_primer_design(
        db,
        planner=planner,
        product_size_range=product_size_range,
        target_tm=target_tm,
    )
    planner = run_restriction_analysis(
        db,
        planner=planner,
        enzymes=enzymes,
    )
    planner = run_assembly_planning(
        db,
        planner=planner,
    )
    planner = run_qc_checks(
        db,
        planner=planner,
        chromatograms=chromatograms,
    )
    return planner


@celery_app.task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def orchestrate_planner_pipeline(
    self,
    planner_id: str,
    *,
    product_size_range: tuple[int, int] | None = None,
    target_tm: float | None = None,
    enzymes: Sequence[str] | None = None,
) -> None:
    """Celery task to orchestrate cloning planner pipeline."""

    db = SessionLocal()
    try:
        record = db.get(models.CloningPlannerSession, UUID(planner_id))
        if not record:
            return
        run_full_pipeline(
            db,
            record,
            product_size_range=product_size_range,
            target_tm=target_tm,
            enzymes=enzymes,
        )
        db.commit()
    except Exception as exc:  # pragma: no cover - Celery handles retries
        db.rollback()
        record = db.get(models.CloningPlannerSession, UUID(planner_id))
        if record:
            record.last_error = str(exc)
            record.status = "errored"
            record.updated_at = _utcnow()
            db.add(record)
            db.commit()
        raise
    finally:
        db.close()


def enqueue_pipeline(
    planner_id: UUID,
    *,
    product_size_range: tuple[int, int] | None = None,
    target_tm: float | None = None,
    enzymes: Sequence[str] | None = None,
) -> None:
    """Schedule cloning planner orchestration via Celery."""

    task_kwargs = {
        "planner_id": str(planner_id),
        "product_size_range": product_size_range,
        "target_tm": target_tm,
        "enzymes": list(enzymes) if enzymes else None,
    }
    if celery_app.conf.task_always_eager:
        orchestrate_planner_pipeline(**task_kwargs)
    else:  # pragma: no cover - exercised in production deployments
        orchestrate_planner_pipeline.delay(**task_kwargs)


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

    guardrail_snapshot = dict(planner.guardrail_state or {})
    if planner.primer_set:
        guardrail_snapshot["primers"] = _primer_guardrail_summary(planner.primer_set)
    if planner.restriction_digest:
        guardrail_snapshot["restriction"] = _restriction_guardrail_summary(planner.restriction_digest)
    if planner.assembly_plan:
        guardrail_snapshot["assembly"] = _assembly_guardrail_summary(planner.assembly_plan)
    if planner.qc_reports:
        guardrail_snapshot["qc"] = _qc_guardrail_summary(planner.qc_reports)
    state_override: dict[str, Any] | None = None
    if guardrail_state is not None:
        state_override = guardrail_state
    guardrail_snapshot = compose_guardrail_state(planner, override=state_override)
    normalised_snapshot = json.loads(json.dumps(guardrail_snapshot))
    planner.guardrail_state = normalised_snapshot
    db.query(models.CloningPlannerSession).filter(models.CloningPlannerSession.id == planner.id).update(
        {"guardrail_state": normalised_snapshot}
    )
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
        "guardrail_state": compose_guardrail_state(planner),
        "stage_timings": planner.stage_timings,
        "current_step": planner.current_step,
        "celery_task_id": planner.celery_task_id,
        "last_error": planner.last_error,
        "created_at": planner.created_at,
        "updated_at": planner.updated_at,
        "completed_at": planner.completed_at,
    }
