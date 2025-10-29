"""Cloning planner orchestration helpers."""

# purpose: provide shared workflow management for multi-stage cloning planner sessions
# status: experimental
# depends_on: backend.app.models, backend.app.schemas

from __future__ import annotations

import asyncio
import hashlib
import json
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any, Callable, Sequence
from uuid import UUID

from celery import chain
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, pubsub, storage
from ..analytics.governance import invalidate_governance_analytics_cache
from ..database import SessionLocal
from ..schemas.sequence_toolkit import SequenceToolkitProfile
from . import sequence_toolkit
from ..tasks import celery_app
from . import qc_ingestion


DEFAULT_TOOLKIT_PROFILE = SequenceToolkitProfile()


def _json_default(value: Any) -> Any:
    """Normalise complex values for JSON serialisation."""

    # purpose: ensure planner payload persistence tolerates datetime objects
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _persist_stage_payload(
    planner: models.CloningPlannerSession,
    step: str,
    payload: Any,
) -> tuple[str | None, dict[str, Any]]:
    """Persist a stage payload to durable storage returning metadata."""

    # purpose: offload large stage payloads to object storage with integrity metadata
    # inputs: planner ORM instance, stage name, arbitrary payload
    # outputs: tuple of storage path (or None) and payload metadata summary
    # status: experimental
    if payload in (None, {}, []):
        return None, {"size_bytes": 0, "content_type": None}
    data = json.dumps(payload, default=_json_default, sort_keys=True).encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    path, size = storage.save_binary_payload(
        data,
        f"{step}_payload.json",
        namespace=f"cloning_planner/{planner.id}/{step}",
        content_type="application/json",
    )
    return path, {
        "size_bytes": size,
        "content_type": "application/json",
        "sha256": digest,
    }


def _derive_stage_metrics(
    step: str,
    guardrail_snapshot: dict[str, Any] | None,
    payload: Any,
) -> dict[str, Any]:
    """Derive lightweight metrics for stage checkpoints."""

    # purpose: store summary metrics aiding governance dashboards and resume flows
    metrics: dict[str, Any] = {}
    guardrail_snapshot = guardrail_snapshot or {}
    if step == "primers":
        metrics["primer_sets"] = guardrail_snapshot.get("primer_sets")
        metrics["primer_warnings"] = guardrail_snapshot.get("primer_warnings")
    elif step == "restriction":
        metrics["restriction_alerts"] = len(guardrail_snapshot.get("restriction_alerts", []))
        metrics["buffer_count"] = len(guardrail_snapshot.get("buffers", []))
    elif step == "assembly":
        metrics["assembly_success"] = guardrail_snapshot.get("assembly_success")
        metrics["ligation_profiles"] = guardrail_snapshot.get("ligation_profiles", [])
    elif step == "qc":
        metrics["qc_checks"] = guardrail_snapshot.get("qc_checks")
        metrics["breach_count"] = len(guardrail_snapshot.get("breaches", []))
    if payload and isinstance(payload, dict):
        metrics.setdefault("payload_keys", sorted(payload.keys()))
    return metrics


def _parse_stage_timestamp(entry: dict[str, Any], key: str) -> datetime | None:
    """Parse ISO8601 timestamps from stage timing entries."""

    # purpose: keep stage history timestamps consistent and timezone-aware
    raw_value = entry.get(key)
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(str(raw_value))
    except ValueError:
        return None


def _persist_stage_record(
    db: Session,
    planner: models.CloningPlannerSession,
    *,
    step: str,
    status: str,
    guardrail_snapshot: dict[str, Any],
    payload: Any,
    task_id: str | None,
    error: str | None,
) -> models.CloningPlannerStageRecord:
    """Persist history entries for planner stages."""

    # purpose: durably record stage outputs, retries, and storage handles
    timings = dict(planner.stage_timings or {})
    timing_entry = dict(timings.get(step) or {})
    attempt_count = (
        db.query(func.count(models.CloningPlannerStageRecord.id))
        .filter(
            models.CloningPlannerStageRecord.session_id == planner.id,
            models.CloningPlannerStageRecord.stage == step,
        )
        .scalar()
    ) or 0
    retries = int(timing_entry.get("retries", 0) or 0)
    payload_path, payload_meta = _persist_stage_payload(planner, step, payload)
    metrics = _derive_stage_metrics(step, guardrail_snapshot, payload)
    record = models.CloningPlannerStageRecord(
        session=planner,
        stage=step,
        status=status,
        attempt=attempt_count,
        retry_count=retries,
        task_id=task_id,
        payload_path=payload_path,
        payload_metadata=payload_meta,
        guardrail_snapshot=guardrail_snapshot,
        metrics=metrics,
        review_state={},
        started_at=_parse_stage_timestamp(timing_entry, "started_at"),
        completed_at=_parse_stage_timestamp(timing_entry, "completed_at"),
        error=error,
    )
    db.add(record)
    db.flush()
    return record


def _dispatch_planner_event(
    planner: models.CloningPlannerSession,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    """Publish planner orchestration updates over the pub/sub channel."""

    # purpose: expose real-time orchestration state to UI clients via Redis pub/sub
    message = {
        "type": event_type,
        "session_id": str(planner.id),
        "status": planner.status,
        "current_step": planner.current_step,
        "guardrail_state": compose_guardrail_state(planner),
        "payload": payload,
        "timestamp": _utcnow().isoformat(),
    }
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(pubsub.publish_planner_event(str(planner.id), message))
        return
    loop.create_task(pubsub.publish_planner_event(str(planner.id), message))

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
    tm_values = [
        p.get("forward", {}).get("thermodynamics", {}).get("tm")
        for p in primers
        if p.get("forward")
    ] + [
        p.get("reverse", {}).get("thermodynamics", {}).get("tm")
        for p in primers
        if p.get("reverse")
    ]
    tm_values = [value for value in tm_values if isinstance(value, (int, float))]
    tm_span = max(tm_values) - min(tm_values) if tm_values else 0.0
    metadata_tags = sorted({
        tag
        for primer in primers
        for tag in primer.get("metadata_tags", [])
    })
    return {
        "primer_sets": len(primers),
        "primer_warnings": warning_count,
        "primer_state": "review" if warning_count else "ok",
        "metadata_tags": metadata_tags,
        "tm_span": tm_span,
    }


def _restriction_guardrail_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Summarise restriction digest compatibility for guardrail tracking."""

    alerts = result.get("alerts", [])
    digests = result.get("digests", [])
    metadata_tags = sorted({
        tag
        for digest in digests
        for tag in digest.get("metadata_tags", [])
    })
    buffers = sorted({
        (digest.get("buffer") or {}).get("name")
        for digest in digests
        if (digest.get("buffer") or {}).get("name")
    })
    kinetics = sorted({
        profile.get("name")
        for digest in digests
        for profile in digest.get("kinetics_profiles", [])
        if profile.get("name")
    })
    return {
        "restriction_alerts": alerts,
        "restriction_state": "review" if alerts else "ok",
        "metadata_tags": metadata_tags,
        "buffers": buffers,
        "kinetics": kinetics,
    }


def _assembly_guardrail_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Summarise assembly simulation outcomes for guardrail tracking."""

    success = result.get("average_success", 0.0)
    state = "ok" if success >= 0.7 else "review"
    steps = result.get("steps", [])
    metadata_tags = sorted({
        tag
        for step in steps
        for tag in step.get("metadata_tags", [])
    })
    ligation_profiles = sorted({
        (step.get("ligation_profile") or {}).get("strategy")
        for step in steps
        if (step.get("ligation_profile") or {}).get("strategy")
    })
    buffers = sorted({
        (step.get("buffer") or {}).get("name")
        for step in steps
        if (step.get("buffer") or {}).get("name")
    })
    kinetics = sorted({
        profile.get("name")
        for step in steps
        for profile in step.get("kinetics_profiles", [])
        if profile.get("name")
    })
    return {
        "assembly_success": success,
        "assembly_state": state,
        "metadata_tags": metadata_tags,
        "ligation_profiles": ligation_profiles,
        "buffers": buffers,
        "kinetics": kinetics,
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
        qc_summary = _qc_guardrail_summary(planner.qc_reports)
        previous_qc = snapshot.get("qc")
        if isinstance(previous_qc, dict) and previous_qc.get("breaches"):
            qc_summary.setdefault("breaches", previous_qc.get("breaches", []))
        snapshot["qc"] = qc_summary
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
        stage_timings={
            "intake": {
                "completed_at": now.isoformat(),
                "status": "intake_recorded",
                "task_id": None,
                "next_step": "primers",
            }
        },
        current_step="intake",
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    db.flush()
    db.refresh(record)
    _dispatch_planner_event(
        record,
        "session_created",
        {"stage": "intake", "status": "intake_recorded"},
    )
    return record


def run_primer_design(
    db: Session,
    *,
    planner: models.CloningPlannerSession,
    product_size_range: tuple[int, int] | None = None,
    target_tm: float | None = None,
    task_id: str | None = None,
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
        task_id=task_id,
    )


def run_restriction_analysis(
    db: Session,
    *,
    planner: models.CloningPlannerSession,
    enzymes: Sequence[str] | None = None,
    task_id: str | None = None,
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
        task_id=task_id,
    )


def run_assembly_planning(
    db: Session,
    *,
    planner: models.CloningPlannerSession,
    strategy: str | None = None,
    task_id: str | None = None,
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
        task_id=task_id,
    )


def run_qc_checks(
    db: Session,
    *,
    planner: models.CloningPlannerSession,
    chromatograms: Sequence[dict[str, Any]] | None = None,
    task_id: str | None = None,
) -> models.CloningPlannerSession:
    """Execute QC evaluation for a planner session."""

    # purpose: gate planner completion on QC checkpoints and chromatogram data
    # inputs: planner record with optional chromatogram descriptors
    # outputs: updated planner with qc payload and guardrail snapshot
    # status: experimental
    profile = DEFAULT_TOOLKIT_PROFILE
    ingestion = qc_ingestion.ingest_chromatograms(db, planner, chromatograms)
    qc_payload = sequence_toolkit.evaluate_qc_reports(
        planner.assembly_plan,
        config=profile,
        chromatograms=ingestion["artifacts"],
    )
    qc_summary = _qc_guardrail_summary(qc_payload)
    qc_summary["breaches"] = ingestion["breaches"]
    guardrail_state = _merge_guardrail_state(
        planner,
        {"qc": qc_summary},
    )
    status = "qc_guardrail_blocked" if ingestion["breaches"] else "qc_complete"
    return record_stage_progress(
        db,
        planner=planner,
        step="qc",
        payload=qc_payload,
        next_step="finalize",
        status=status,
        guardrail_state=guardrail_state,
        task_id=task_id,
        artifacts=ingestion.get("records"),
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
    _mark_stage_started(db, planner, "primers", task_id=None)
    planner = run_primer_design(
        db,
        planner=planner,
        product_size_range=product_size_range,
        target_tm=target_tm,
    )
    _mark_stage_started(db, planner, "restriction", task_id=None)
    planner = run_restriction_analysis(
        db,
        planner=planner,
        enzymes=enzymes,
    )
    _mark_stage_started(db, planner, "assembly", task_id=None)
    planner = run_assembly_planning(
        db,
        planner=planner,
    )
    _mark_stage_started(db, planner, "qc", task_id=None)
    planner = run_qc_checks(
        db,
        planner=planner,
        chromatograms=chromatograms,
    )
    planner = _complete_pipeline_stage(db, planner, task_id=None)
    return planner


def _mark_stage_started(
    db: Session,
    planner: models.CloningPlannerSession,
    stage: str,
    *,
    task_id: str | None,
) -> models.CloningPlannerSession:
    """Record the start of a pipeline stage for checkpoint tracking."""

    # purpose: capture resumable checkpoint metadata before stage execution
    now = _utcnow()
    timings = dict(planner.stage_timings or {})
    entry = dict(timings.get(stage) or {})
    previous_runs = entry.get("retries", 0)
    if entry:
        previous_runs += 1
    entry.update(
        {
            "started_at": now.isoformat(),
            "status": f"{stage}_running",
            "retries": previous_runs,
            "error": None,
        }
    )
    if task_id is not None:
        entry["task_id"] = task_id
    else:
        entry.setdefault("task_id", None)
    timings[stage] = entry
    planner.stage_timings = timings
    planner.current_step = stage
    planner.status = f"{stage}_running"
    if task_id is not None:
        planner.celery_task_id = task_id
    planner.updated_at = now
    db.add(planner)
    db.flush()
    _dispatch_planner_event(
        planner,
        "stage_started",
        {"stage": stage, "task_id": task_id},
    )
    return planner


def _record_stage_failure(
    db: Session,
    planner: models.CloningPlannerSession,
    stage: str,
    exc: Exception,
    *,
    task_id: str | None,
) -> None:
    """Persist failure metadata when a stage errors during execution."""

    now = _utcnow()
    timings = dict(planner.stage_timings or {})
    entry = dict(timings.get(stage) or {})
    entry.update(
        {
            "status": f"{stage}_errored",
            "error": str(exc),
            "completed_at": now.isoformat(),
        }
    )
    if task_id is not None:
        entry["task_id"] = task_id
    timings[stage] = entry
    planner.stage_timings = timings
    planner.status = "errored"
    planner.last_error = str(exc)
    planner.updated_at = now
    if task_id is not None:
        planner.celery_task_id = task_id
    db.add(planner)
    record = _persist_stage_record(
        db,
        planner,
        step=stage,
        status=f"{stage}_errored",
        guardrail_snapshot={},
        payload={},
        task_id=task_id,
        error=str(exc),
    )
    db.commit()
    _dispatch_planner_event(
        planner,
        "stage_failed",
        {"stage": stage, "error": str(exc), "record_id": str(record.id)},
    )


def _complete_pipeline_stage(
    db: Session,
    planner: models.CloningPlannerSession,
    *,
    task_id: str | None,
) -> models.CloningPlannerSession:
    """Summarise guardrail state and mark pipeline completion checkpoint."""

    guardrails = compose_guardrail_state(planner)
    planner.guardrail_state = guardrails
    qc_breaches = guardrails.get("qc", {}).get("breaches", [])
    status = "qc_guardrail_blocked" if qc_breaches else "ready_for_finalize"
    now = _utcnow()
    timings = dict(planner.stage_timings or {})
    entry = dict(timings.get("finalize") or {})
    entry.update(
        {
            "status": status,
            "completed_at": now.isoformat(),
            "task_id": task_id,
            "guardrail": guardrails.get("qc"),
            "error": None,
        }
    )
    timings["finalize"] = entry
    planner.stage_timings = timings
    planner.status = status
    planner.current_step = "finalize"
    planner.updated_at = now
    if task_id is not None:
        planner.celery_task_id = task_id
    if status == "qc_guardrail_blocked":
        invalidate_governance_analytics_cache(execution_ids=[planner.id])
    db.add(planner)
    record = _persist_stage_record(
        db,
        planner,
        step="finalize",
        status=status,
        guardrail_snapshot=guardrails,
        payload=guardrails,
        task_id=task_id,
        error=None,
    )
    db.flush()
    db.refresh(planner)
    _dispatch_planner_event(
        planner,
        "stage_completed",
        {"stage": "finalize", "record_id": str(record.id), "status": status},
    )
    return planner


def _execute_stage_task(
    task,
    planner_id: str,
    stage: str,
    runner: Callable[[Session, models.CloningPlannerSession, str | None], models.CloningPlannerSession],
) -> str:
    """Execute a planner stage within a Celery worker context."""

    db = SessionLocal()
    planner: models.CloningPlannerSession | None = None
    task_id = getattr(task.request, "id", None)
    try:
        planner = db.get(models.CloningPlannerSession, UUID(planner_id))
        if not planner:
            return planner_id
        _mark_stage_started(db, planner, stage, task_id=task_id)
        planner = runner(db, planner, task_id)
        db.commit()
        return str(planner.id)
    except Exception as exc:  # pragma: no cover - Celery handles retries
        db.rollback()
        if planner is None:
            planner = db.get(models.CloningPlannerSession, UUID(planner_id))
        if planner is not None:
            _record_stage_failure(db, planner, stage, exc, task_id=task_id)
        raise
    finally:
        db.close()


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    name="app.workers.cloning_planner.primer_stage",
)
def primer_stage_task(
    self,
    planner_id: str,
    *,
    product_size_range: tuple[int, int] | None = None,
    target_tm: float | None = None,
) -> str:
    """Celery task for primer design stage."""

    return _execute_stage_task(
        self,
        planner_id,
        "primers",
        lambda db, planner, task_id: run_primer_design(
            db,
            planner=planner,
            product_size_range=product_size_range,
            target_tm=target_tm,
            task_id=task_id,
        ),
    )


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    name="app.workers.cloning_planner.restriction_stage",
)
def restriction_stage_task(
    self,
    planner_id: str,
    *,
    enzymes: Sequence[str] | None = None,
) -> str:
    """Celery task for restriction digest stage."""

    enzyme_list: Sequence[str] | None = list(enzymes) if enzymes else None
    return _execute_stage_task(
        self,
        planner_id,
        "restriction",
        lambda db, planner, task_id: run_restriction_analysis(
            db,
            planner=planner,
            enzymes=enzyme_list,
            task_id=task_id,
        ),
    )


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    name="app.workers.cloning_planner.assembly_stage",
)
def assembly_stage_task(
    self,
    planner_id: str,
    *,
    strategy: str | None = None,
) -> str:
    """Celery task for assembly planning stage."""

    return _execute_stage_task(
        self,
        planner_id,
        "assembly",
        lambda db, planner, task_id: run_assembly_planning(
            db,
            planner=planner,
            strategy=strategy,
            task_id=task_id,
        ),
    )


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    name="app.workers.cloning_planner.qc_stage",
)
def qc_stage_task(
    self,
    planner_id: str,
    *,
    chromatograms: Sequence[dict[str, Any]] | None = None,
) -> str:
    """Celery task for QC evaluation stage."""

    chroma_payload = list(chromatograms) if chromatograms else None
    return _execute_stage_task(
        self,
        planner_id,
        "qc",
        lambda db, planner, task_id: run_qc_checks(
            db,
            planner=planner,
            chromatograms=chroma_payload,
            task_id=task_id,
        ),
    )


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
    name="app.workers.cloning_planner.finalize_stage",
)
def finalize_stage_task(self, planner_id: str) -> str:
    """Celery task to summarise guardrails after QC completion."""

    return _execute_stage_task(
        self,
        planner_id,
        "finalize",
        lambda db, planner, task_id: _complete_pipeline_stage(
            db,
            planner,
            task_id=task_id,
        ),
    )


def _prepare_enqueued_state(planner_id: UUID, stage: str) -> None:
    """Initialise queue metadata for a planner stage."""

    db = SessionLocal()
    try:
        record = db.get(models.CloningPlannerSession, planner_id)
        if not record:
            return
        now = _utcnow()
        timings = dict(record.stage_timings or {})
        entry = dict(timings.get(stage) or {})
        entry.update(
            {
                "status": f"{stage}_queued",
                "queued_at": now.isoformat(),
                "error": None,
            }
        )
        entry.setdefault("task_id", None)
        timings[stage] = entry
        record.stage_timings = timings
        record.current_step = stage
        record.status = f"{stage}_queued"
        record.celery_task_id = None
        record.updated_at = now
        db.add(record)
        db.commit()
    finally:
        db.close()


def _assign_task_reference(planner_id: UUID, task_id: str | None) -> None:
    """Persist Celery task identifiers for orchestration tracking."""

    db = SessionLocal()
    try:
        record = db.get(models.CloningPlannerSession, planner_id)
        if not record:
            return
        stage = record.current_step or "primers"
        timings = dict(record.stage_timings or {})
        entry = dict(timings.get(stage) or {})
        entry["task_id"] = task_id
        timings[stage] = entry
        record.stage_timings = timings
        record.celery_task_id = task_id
        record.updated_at = _utcnow()
        db.add(record)
        db.commit()
    finally:
        db.close()


def enqueue_pipeline(
    planner_id: UUID,
    *,
    product_size_range: tuple[int, int] | None = None,
    target_tm: float | None = None,
    enzymes: Sequence[str] | None = None,
    chromatograms: Sequence[dict[str, Any]] | None = None,
    resume_from: str | None = None,
) -> str | None:
    """Schedule cloning planner orchestration via Celery."""

    start_stage = (resume_from or "primers").lower()
    if start_stage == "intake":
        start_stage = "primers"
    stage_plan = [
        (
            "primers",
            primer_stage_task.s(
                str(planner_id),
                product_size_range=product_size_range,
                target_tm=target_tm,
            ),
        ),
        (
            "restriction",
            restriction_stage_task.s(enzymes=list(enzymes) if enzymes else None),
        ),
        (
            "assembly",
            assembly_stage_task.s(),
        ),
        (
            "qc",
            qc_stage_task.s(chromatograms=list(chromatograms) if chromatograms else None),
        ),
        (
            "finalize",
            finalize_stage_task.s(),
        ),
    ]
    start_index = next((idx for idx, (name, _) in enumerate(stage_plan) if name == start_stage), 0)
    signatures = [sig.clone() for _, sig in stage_plan[start_index:]]
    if signatures:
        if start_index > 0:
            existing_args = tuple(signatures[0].args or ())
            signatures[0].args = (str(planner_id),) + existing_args
    if not signatures:
        return None
    _prepare_enqueued_state(planner_id, stage_plan[start_index][0])
    pipeline = chain(*signatures)
    if celery_app.conf.task_always_eager:
        result = pipeline.apply()
    else:  # pragma: no cover - exercised in production deployments
        result = pipeline.apply_async()
    task_id = getattr(result, "id", None)
    _assign_task_reference(planner_id, task_id)
    return task_id


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
    artifacts: Sequence[models.CloningPlannerQCArtifact] | None = None,
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
        qc_state = _qc_guardrail_summary(planner.qc_reports)
        qc_state.setdefault("breaches", [])
        guardrail_snapshot["qc"] = qc_state
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
    checkpoint_payload = dict(planner.stage_timings.get(step) or {})
    checkpoint_payload.update(
        {
            "completed_at": now.isoformat(),
            "status": status,
            "task_id": task_id,
            "next_step": next_step,
            "error": error,
        }
    )
    guardrail_key = guardrail_snapshot.get(step)
    if isinstance(guardrail_key, dict):
        checkpoint_payload["guardrail"] = guardrail_key
    planner.stage_timings[step] = checkpoint_payload
    planner.updated_at = now
    if next_step:
        planner.current_step = next_step
    resolved_status = status or f"{step}_completed"
    planner.status = resolved_status
    if resolved_status in {"finalized", "completed"}:
            planner.completed_at = now
    db.add(planner)
    stage_guardrail = guardrail_snapshot.get(step)
    record = _persist_stage_record(
        db,
        planner,
        step=step,
        status=resolved_status,
        guardrail_snapshot=stage_guardrail if isinstance(stage_guardrail, dict) else {},
        payload=payload,
        task_id=task_id,
        error=error,
    )
    if artifacts:
        qc_ingestion.attach_artifacts_to_stage(db, artifacts, record)
    db.flush()
    db.refresh(planner)
    _dispatch_planner_event(
        planner,
        "stage_completed",
        {
            "stage": step,
            "status": resolved_status,
            "record_id": str(record.id),
            "task_id": task_id,
        },
    )
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
    record = _persist_stage_record(
        db,
        planner,
        step="finalize",
        status="finalized",
        guardrail_snapshot=planner.guardrail_state or {},
        payload=planner.guardrail_state or {},
        task_id=None,
        error=None,
    )
    db.flush()
    db.refresh(planner)
    _dispatch_planner_event(
        planner,
        "session_finalized",
        {"stage": "finalize", "record_id": str(record.id), "status": "finalized"},
    )
    return planner


def _serialise_stage_record(record: models.CloningPlannerStageRecord) -> dict[str, Any]:
    """Convert a stage record ORM instance into serialisable metadata."""

    # purpose: surface durable checkpoint lineage for UI consumers
    return {
        "id": record.id,
        "stage": record.stage,
        "attempt": record.attempt,
        "retry_count": record.retry_count,
        "status": record.status,
        "task_id": record.task_id,
        "payload_path": record.payload_path,
        "payload_metadata": record.payload_metadata,
        "guardrail_snapshot": record.guardrail_snapshot,
        "metrics": record.metrics,
        "review_state": record.review_state,
        "started_at": record.started_at,
        "completed_at": record.completed_at,
        "error": record.error,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


def _serialise_qc_artifact(artifact: models.CloningPlannerQCArtifact) -> dict[str, Any]:
    """Convert QC artifact ORM rows into API payloads."""

    # purpose: expose QC ingestion lineage, guardrail thresholds, and reviewer loops
    return {
        "id": artifact.id,
        "artifact_name": artifact.artifact_name,
        "sample_id": artifact.sample_id,
        "trace_path": artifact.trace_path,
        "storage_path": artifact.storage_path,
        "metrics": artifact.metrics,
        "thresholds": artifact.thresholds,
        "stage_record_id": artifact.stage_record_id,
        "reviewer_id": artifact.reviewer_id,
        "reviewer_decision": artifact.reviewer_decision,
        "reviewer_notes": artifact.reviewer_notes,
        "reviewed_at": artifact.reviewed_at,
        "created_at": artifact.created_at,
        "updated_at": artifact.updated_at,
    }


def serialize_session(planner: models.CloningPlannerSession) -> dict[str, Any]:
    """Render a cloning planner session into a JSON-serialisable dict."""

    # purpose: provide consistent API responses for planner session payloads
    # inputs: CloningPlannerSession ORM instance
    # outputs: dictionary for JSON responses
    # status: experimental
    stage_history = [
        _serialise_stage_record(record)
        for record in sorted(planner.stage_history or [], key=lambda item: item.created_at or datetime.min)
    ]
    qc_artifacts = [
        _serialise_qc_artifact(artifact)
        for artifact in sorted(planner.qc_artifacts or [], key=lambda item: item.created_at or datetime.min)
    ]
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
        "stage_history": stage_history,
        "qc_artifacts": qc_artifacts,
    }
