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
from uuid import UUID, uuid4

from celery import chain
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

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


def _toolkit_snapshot_from_profile(
    profile: dict[str, Any] | None, fallback: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Normalize toolkit profile metadata for guardrail state."""

    # purpose: centralize preset metadata persistence across planner stages
    effective_profile: dict[str, Any] = {}
    if fallback:
        effective_profile.update(fallback)
    if profile:
        for key, value in profile.items():
            if value not in (None, "", [], {}):
                effective_profile[key] = value
            elif key not in effective_profile:
                effective_profile[key] = value
    if not effective_profile:
        return {}
    return {
        "preset_id": effective_profile.get("preset_id"),
        "preset_name": effective_profile.get("preset_name"),
        "preset_description": effective_profile.get("preset_description"),
        "metadata_tags": effective_profile.get("metadata_tags", []),
        "recommended_use": effective_profile.get("recommended_use", []),
        "notes": effective_profile.get("notes", []),
        "profile": effective_profile,
    }


def _resolve_toolkit_preset(
    planner: models.CloningPlannerSession,
    override: str | None = None,
) -> str | None:
    """Determine the toolkit preset to apply for the planner session."""

    # purpose: align primer/restriction presets with assembly strategies and sequence traits
    if override:
        return override
    state = planner.guardrail_state or {}
    toolkit_state = state.get("toolkit") if isinstance(state, dict) else None
    if isinstance(toolkit_state, dict):
        existing = toolkit_state.get("preset_id")
        if existing:
            return existing
    strategy = (planner.assembly_strategy or "").lower()
    if strategy in {"golden_gate", "golden gate"}:
        return "multiplex"
    if strategy in {"qpcr", "qpcr_validation", "qpcr-validation"}:
        return "qpcr"
    sequences = planner.input_sequences or []
    for descriptor in sequences:
        sequence = descriptor.get("sequence") if isinstance(descriptor, dict) else None
        if not sequence:
            continue
        metrics = sequence_toolkit.compute_sequence_metrics(sequence)
        if metrics.get("gc_content", 0.0) >= 65.0:
            return "high_gc"
    return None


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
        metrics["multiplex_risk"] = guardrail_snapshot.get("multiplex_risk")
        metrics["preset_id"] = guardrail_snapshot.get("preset_id")
        metrics["cross_dimer_flags"] = guardrail_snapshot.get(
            "cross_dimer_flags"
        )
    elif step == "restriction":
        metrics["restriction_alerts"] = len(guardrail_snapshot.get("restriction_alerts", []))
        metrics["buffer_count"] = len(guardrail_snapshot.get("buffers", []))
        metrics["best_strategy"] = guardrail_snapshot.get("best_strategy")
        metrics["strategy_scores"] = guardrail_snapshot.get("strategy_scores")
    elif step == "assembly":
        metrics["assembly_success"] = guardrail_snapshot.get("assembly_success")
        metrics["ligation_profiles"] = guardrail_snapshot.get("ligation_profiles", [])
        metrics["preset_id"] = guardrail_snapshot.get("preset_id")
    elif step == "qc":
        metrics["qc_checks"] = guardrail_snapshot.get("qc_checks")
        metrics["breach_count"] = len(guardrail_snapshot.get("breaches", []))
        metrics["preset_id"] = guardrail_snapshot.get("preset_id")
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
    branch_id: UUID | None = None,
    checkpoint_key: str | None = None,
    checkpoint_payload: dict[str, Any] | None = None,
    guardrail_transition: dict[str, Any] | None = None,
    timeline_position: str | None = None,
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
        branch_id=branch_id,
        checkpoint_key=checkpoint_key,
        checkpoint_payload=checkpoint_payload or {},
        guardrail_transition=guardrail_transition or {},
        timeline_position=timeline_position,
    )
    db.add(record)
    db.flush()
    return record


def _dispatch_planner_event(
    planner: models.CloningPlannerSession,
    event_type: str,
    payload: dict[str, Any],
    *,
    previous_guardrail_gate: dict[str, Any] | None = None,
    branch_id: UUID | None = None,
    checkpoint: dict[str, Any] | None = None,
    event_id: str | None = None,
) -> str:
    """Publish planner orchestration updates over the pub/sub channel."""

    # purpose: expose real-time orchestration state to UI clients via Redis pub/sub
    active_branch, branch_state = _ensure_branch_state(planner)
    guardrail_state = compose_guardrail_state(planner)
    guardrail_gate = _evaluate_guardrail_gate(guardrail_state)
    event_identifier = event_id or str(uuid4())
    planner.timeline_cursor = event_identifier
    branch_ref = branch_id or active_branch
    guardrail_transition = {
        "previous": previous_guardrail_gate,
        "current": guardrail_gate,
    }
    message = {
        "id": event_identifier,
        "type": event_type,
        "session_id": str(planner.id),
        "status": planner.status,
        "current_step": planner.current_step,
        "guardrail_state": guardrail_state,
        "guardrail_gate": guardrail_gate,
        "guardrail_transition": guardrail_transition,
        "payload": payload,
        "branch": {
            "active": str(branch_ref) if branch_ref else None,
            "state": branch_state,
        },
        "checkpoint": checkpoint,
        "timeline_cursor": event_identifier,
        "timestamp": _utcnow().isoformat(),
    }
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(pubsub.publish_planner_event(str(planner.id), message))
        return event_identifier
    loop.create_task(pubsub.publish_planner_event(str(planner.id), message))
    return event_identifier

def _merge_guardrail_state(
    planner: models.CloningPlannerSession, updates: dict[str, Any]
) -> dict[str, Any]:
    """Merge guardrail updates into the planner state."""

    # purpose: keep guardrail snapshots cumulative across orchestration stages
    base = dict(planner.guardrail_state or {})
    for key, value in updates.items():
        if key == "toolkit":
            existing_toolkit = (
                base.get("toolkit") if isinstance(base.get("toolkit"), dict) else {}
            )
            if isinstance(value, dict) and value:
                merged_toolkit = dict(existing_toolkit)
                merged_toolkit.update(value)
                base["toolkit"] = merged_toolkit
            elif "toolkit" not in base:
                base["toolkit"] = {}
            continue
        base[key] = value
    return base


def _merge_with_defaults(
    payload: dict[str, Any] | None, defaults: dict[str, Any]
) -> dict[str, Any]:
    """Apply default schema fields to planner payloads."""

    merged = json.loads(json.dumps(defaults))
    if isinstance(payload, dict):
        merged.update(payload)
    return merged


def _ensure_branch_state(
    planner: models.CloningPlannerSession,
) -> tuple[UUID, dict[str, Any]]:
    """Ensure planner branch metadata has an active branch entry."""

    # purpose: guarantee branch metadata exists for SSE and stage history mapping
    branch_state = dict(planner.branch_state or {})
    branches = branch_state.get("branches")
    if not isinstance(branches, dict):
        branches = {}
    active_branch_id = planner.active_branch_id or planner.id
    if isinstance(active_branch_id, str):
        try:
            active_branch_id = UUID(active_branch_id)
        except (ValueError, TypeError):  # pragma: no cover - defensive parsing
            active_branch_id = planner.id
    branch_key = str(active_branch_id)
    if branch_key not in branches:
        created_at = (planner.created_at or _utcnow()).isoformat()
        branches[branch_key] = {
            "id": branch_key,
            "label": "main",
            "status": "active",
            "parent_id": None,
            "created_at": created_at,
        }
    branch_state["branches"] = branches
    order = branch_state.get("order")
    if not isinstance(order, list):
        order = []
    if branch_key not in order:
        order.append(branch_key)
    branch_state["order"] = order
    planner.branch_state = branch_state
    planner.active_branch_id = active_branch_id
    return active_branch_id, branch_state


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
    profile = result.get("profile") or {}
    multiplex = result.get("multiplex") or {}
    metadata_tags = sorted({
        tag
        for primer in primers
        for tag in primer.get("metadata_tags", [])
    } | set(multiplex.get("metadata_tags", []) or []) | set(profile.get("metadata_tags", []) or []))
    state = "blocked" if multiplex.get("risk_level") == "blocked" else (
        "review" if warning_count or multiplex.get("risk_level") == "review" else "ok"
    )
    return {
        "primer_sets": len(primers),
        "primer_warnings": warning_count,
        "primer_state": state,
        "metadata_tags": metadata_tags,
        "tm_span": tm_span,
        "multiplex_risk": multiplex.get("risk_level"),
        "cross_dimer_flags": len(multiplex.get("cross_dimer_flags", [])),
        "recommended_use": multiplex.get("recommended_use")
        or profile.get("recommended_use", []),
        "notes": multiplex.get("notes", []),
        "preset_id": profile.get("preset_id"),
        "profile": profile,
    }


def _restriction_guardrail_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Summarise restriction digest compatibility for guardrail tracking."""

    alerts = result.get("alerts", [])
    digests = result.get("digests", [])
    profile = result.get("profile") or {}
    strategies = result.get("strategy_scores", [])
    metadata_tags = sorted({
        tag
        for digest in digests
        for tag in digest.get("metadata_tags", [])
    } | set(profile.get("metadata_tags", []) or []))
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
    state = "review" if alerts else "ok"
    best_strategy = None
    for entry in strategies:
        compatibility = entry.get("compatibility", 0.0)
        hint = entry.get("guardrail_hint", "") or ""
        if best_strategy is None or compatibility > best_strategy.get("compatibility", 0.0):
            best_strategy = entry
        if "blocked" in hint.lower() or compatibility < 0.4:
            state = "blocked"
        elif state != "blocked" and ("requires" in hint.lower() or compatibility < 0.7):
            state = "review"
    return {
        "restriction_alerts": alerts,
        "restriction_state": state,
        "metadata_tags": metadata_tags,
        "buffers": buffers,
        "kinetics": kinetics,
        "strategy_scores": strategies,
        "best_strategy": best_strategy,
        "preset_id": profile.get("preset_id"),
        "profile": profile,
    }


def _assembly_guardrail_summary(result: dict[str, Any]) -> dict[str, Any]:
    """Summarise assembly simulation outcomes for guardrail tracking."""

    success = result.get("average_success", 0.0)
    state = "ok" if success >= 0.7 else "review"
    steps = result.get("steps", [])
    profile = result.get("profile") or {}
    metadata_tags = sorted({
        tag
        for step in steps
        for tag in step.get("metadata_tags", [])
    } | set(profile.get("metadata_tags", []) or []))
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
    if success < 0.5:
        state = "blocked"
    return {
        "assembly_success": success,
        "assembly_state": state,
        "metadata_tags": metadata_tags,
        "ligation_profiles": ligation_profiles,
        "buffers": buffers,
        "kinetics": kinetics,
        "preset_id": profile.get("preset_id"),
        "recommended_use": profile.get("recommended_use", []),
        "profile": profile,
    }


def _qc_guardrail_summary(result: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any]:
    """Summarise QC checkpoints for guardrail tracking."""

    if isinstance(result, dict):
        reports = result.get("reports", [])
        profile = result.get("profile") or {}
    else:
        reports = result
        profile = {}
    statuses = {entry.get("status") for entry in reports}
    state = "ok" if statuses <= {"pass"} else "review"
    return {
        "qc_state": state,
        "qc_checks": len(reports),
        "preset_id": profile.get("preset_id"),
        "profile": profile,
    }


def compose_guardrail_state(
    planner: models.CloningPlannerSession,
    override: dict[str, Any] | None = None,
    *,
    base_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an aggregated guardrail snapshot from planner outputs."""

    snapshot_source = base_snapshot if base_snapshot is not None else planner.guardrail_state or {}
    snapshot = dict(snapshot_source)
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
        for key, value in override.items():
            snapshot[key] = value

    qc_section = dict(snapshot.get("qc") or {})
    custody_state = snapshot.get("custody")
    override_backpressure = bool((override or {}).get("qc_backpressure"))
    if isinstance(custody_state, dict):
        open_counts = custody_state.get("open_counts") or {}
        open_drill = custody_state.get("open_drill_count") or 0
        recovery_gate = custody_state.get("recovery_gate")
        custody_backpressure = bool(
            custody_state.get("qc_backpressure")
            or override_backpressure
            or open_drill
            or open_counts.get("critical")
            or recovery_gate
        )
        if custody_backpressure:
            qc_section["qc_backpressure"] = True
        snapshot["custody_status"] = custody_state.get("status") or custody_state.get("guardrail_status")
        snapshot["custody_event_overlays"] = custody_state.get("event_overlays", {})
        snapshot["custody_open_counts"] = open_counts
        snapshot["custody_execution_id"] = custody_state.get("execution_id")
        snapshot.setdefault("custody", custody_state)
    elif override_backpressure:
        qc_section["qc_backpressure"] = True
    snapshot["qc"] = qc_section
    snapshot["qc_backpressure"] = bool(qc_section.get("qc_backpressure"))
    return snapshot


class GuardrailBackpressureError(RuntimeError):
    """Raised when custody guardrails enforce planner backpressure."""


def _load_protocol_guardrail_snapshot(
    db: Session, planner: models.CloningPlannerSession
) -> dict[str, Any]:
    """Fetch custody guardrail overlays linked to a planner session."""

    if not planner.protocol_execution_id:
        return {}
    execution = (
        db.query(models.ProtocolExecution)
        .options(joinedload(models.ProtocolExecution.template))
        .filter(models.ProtocolExecution.id == planner.protocol_execution_id)
        .first()
    )
    if not execution:
        return {}
    state = dict(execution.guardrail_state or {})
    custody_payload = dict((execution.result or {}).get("custody", {}))
    open_counts = dict(state.get("open_counts") or custody_payload.get("open_severity_counts") or {})
    open_escalations = int(
        state.get("open_escalations")
        or custody_payload.get("open_escalations")
        or sum(open_counts.values() or [0])
    )
    open_drill_count = int(
        state.get("open_drill_count")
        or custody_payload.get("open_drill_count")
        or 0
    )
    recovery_gate = bool(state.get("recovery_gate") or custody_payload.get("recovery_gate"))
    qc_backpressure = bool(
        state.get("qc_backpressure")
        or custody_payload.get("qc_backpressure")
        or open_drill_count
        or open_counts.get("critical")
        or recovery_gate
    )
    snapshot = {
        "execution_id": str(execution.id),
        "template_id": str(execution.template_id) if execution.template_id else None,
        "team_id": str(execution.template.team_id) if execution.template else None,
        "status": execution.guardrail_status or "stable",
        "qc_backpressure": qc_backpressure,
        "open_counts": open_counts,
        "open_escalations": open_escalations,
        "open_drill_count": open_drill_count,
        "recovery_gate": recovery_gate,
        "event_overlays": state.get("event_overlays")
        or custody_payload.get("event_overlays")
        or {},
        "last_synced_at": state.get("last_synced_at")
        or custody_payload.get("last_synced_at"),
    }
    if custody_payload:
        snapshot["custody_payload"] = custody_payload
    return snapshot


def refresh_planner_guardrails(
    db: Session,
    planner: models.CloningPlannerSession,
    *,
    base_snapshot: dict[str, Any] | None = None,
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Recompute planner guardrail state incorporating custody overlays."""

    override_payload = dict(override or {})
    protocol_snapshot = _load_protocol_guardrail_snapshot(db, planner)
    if protocol_snapshot:
        override_payload["custody"] = protocol_snapshot
        override_payload.setdefault("custody_status", protocol_snapshot.get("status"))
        if protocol_snapshot.get("qc_backpressure"):
            override_payload["qc_backpressure"] = True
    aggregated = compose_guardrail_state(
        planner,
        override=override_payload or None,
        base_snapshot=base_snapshot,
    )
    normalised = json.loads(json.dumps(aggregated, default=_json_default))
    planner.guardrail_state = normalised
    db.query(models.CloningPlannerSession).filter(
        models.CloningPlannerSession.id == planner.id
    ).update({"guardrail_state": normalised})
    db.flush()
    return normalised


def _evaluate_guardrail_gate(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Derive guardrail gating metadata for downstream consumers."""

    custody_status_raw = snapshot.get("custody_status") or ""
    custody_status = custody_status_raw.lower() or None
    qc_backpressure = bool(snapshot.get("qc_backpressure"))
    custody_snapshot = snapshot.get("custody") or {}
    open_drill_count = int(custody_snapshot.get("open_drill_count") or 0)
    open_escalations = int(custody_snapshot.get("open_escalations") or 0)
    reasons: list[str] = []
    if custody_status in {"halted", "alert"}:
        reasons.append(f"custody_status:{custody_status}")
    if qc_backpressure and "qc_backpressure" not in reasons:
        reasons.append("qc_backpressure")
    if open_drill_count and "open_drill" not in reasons:
        reasons.append("open_drill")
    return {
        "active": bool(reasons),
        "reasons": reasons,
        "custody_status": custody_status,
        "qc_backpressure": qc_backpressure,
        "open_drill_count": open_drill_count,
        "open_escalations": open_escalations,
    }


def _record_guardrail_hold(
    db: Session,
    planner: models.CloningPlannerSession,
    stage: str,
    gate: dict[str, Any],
    *,
    task_id: str | None,
) -> None:
    """Persist guardrail hold metadata and emit orchestration events."""

    active_branch_id, _ = _ensure_branch_state(planner)
    hold_gate = json.loads(json.dumps(gate, default=_json_default))
    previous_gate = _evaluate_guardrail_gate(planner.guardrail_state or {})
    now = _utcnow()
    timings = dict(planner.stage_timings or {})
    entry = dict(timings.get(stage) or {})
    entry.setdefault("queued_at", now.isoformat())
    entry.update(
        {
            "status": f"{stage}_guardrail_hold",
            "hold_reason": hold_gate,
            "task_id": task_id,
            "error": None,
            "branch_id": str(active_branch_id) if active_branch_id else None,
        }
    )
    timings[stage] = entry
    planner.stage_timings = timings
    planner.status = f"{stage}_guardrail_hold"
    planner.current_step = stage
    planner.updated_at = now
    if task_id is not None:
        planner.celery_task_id = task_id
    db.add(planner)
    db.flush()
    event_id = str(uuid4())
    _dispatch_planner_event(
        planner,
        "guardrail_hold",
        {"stage": stage, "gate": hold_gate, "task_id": task_id},
        previous_guardrail_gate=previous_gate,
        branch_id=active_branch_id,
        checkpoint={"key": stage, "payload": entry},
        event_id=event_id,
    )


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
    protocol_execution_id: UUID | None = None,
    input_sequences: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
    toolkit_preset: str | None = None,
) -> models.CloningPlannerSession:
    """Initialise a cloning planner session with intake context."""

    # purpose: seed resumable planner session rows prior to background orchestration
    # inputs: db session, optional creator, assembly strategy choice, optional sequences and metadata
    # outputs: persisted CloningPlannerSession ORM instance
    # status: experimental
    now = _utcnow()
    execution_id = protocol_execution_id
    if execution_id is None and metadata:
        raw_execution = metadata.get("protocol_execution_id")
        if raw_execution:
            with suppress(ValueError, TypeError):
                execution_id = UUID(str(raw_execution))
    guardrail_state = dict(metadata.get("guardrail_state", {})) if metadata else {}
    if toolkit_preset:
        guardrail_state["toolkit"] = _toolkit_snapshot_from_profile(
            {
                "preset_id": toolkit_preset,
                "metadata_tags": [f"preset:{toolkit_preset}"],
                "recommended_use": [],
                "notes": [],
            }
        )
    branch_identifier = uuid4()
    record = models.CloningPlannerSession(
        created_by_id=getattr(created_by, "id", None),
        assembly_strategy=assembly_strategy,
        protocol_execution_id=execution_id,
        input_sequences=list(input_sequences or []),
        guardrail_state=guardrail_state,
        stage_timings={
            "intake": {
                "completed_at": now.isoformat(),
                "status": "intake_recorded",
                "task_id": None,
                "next_step": "primers",
                "branch_id": str(branch_identifier),
            }
        },
        current_step="intake",
        branch_state={
            "branches": {
                str(branch_identifier): {
                    "id": str(branch_identifier),
                    "label": "main",
                    "status": "active",
                    "parent_id": None,
                    "created_at": now.isoformat(),
                }
            },
            "order": [str(branch_identifier)],
        },
        active_branch_id=branch_identifier,
        timeline_cursor=None,
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    db.flush()
    db.refresh(record)
    _ensure_branch_state(record)
    checkpoint_payload = record.stage_timings.get("intake", {})
    event_id = str(uuid4())
    _dispatch_planner_event(
        record,
        "session_created",
        {"stage": "intake", "status": "intake_recorded"},
        previous_guardrail_gate=_evaluate_guardrail_gate(record.guardrail_state or {}),
        branch_id=record.active_branch_id,
        checkpoint={"key": "intake", "payload": checkpoint_payload},
        event_id=event_id,
    )
    return record


def run_primer_design(
    db: Session,
    *,
    planner: models.CloningPlannerSession,
    product_size_range: tuple[int, int] | None = None,
    target_tm: float | None = None,
    preset_id: str | None = None,
    task_id: str | None = None,
) -> models.CloningPlannerSession:
    """Execute primer design stage for a planner session."""

    # purpose: derive primer sets via Primer3 for planner sequences
    # inputs: planner record and optional primer sizing overrides
    # outputs: updated planner with primer_set payload and guardrail summary
    # status: experimental
    profile = DEFAULT_TOOLKIT_PROFILE
    resolved_preset = _resolve_toolkit_preset(planner, override=preset_id)
    primer_payload = sequence_toolkit.design_primers(
        planner.input_sequences,
        config=profile,
        product_size_range=product_size_range or (80, 280),
        target_tm=target_tm or 60.0,
        preset_id=resolved_preset,
    )
    toolkit_snapshot = _toolkit_snapshot_from_profile(
        primer_payload.get("profile")
    )
    guardrail_state = _merge_guardrail_state(
        planner,
        {
            "primers": _primer_guardrail_summary(primer_payload),
            "toolkit": toolkit_snapshot,
        },
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
    preset_id: str | None = None,
    task_id: str | None = None,
) -> models.CloningPlannerSession:
    """Execute restriction digest analysis for a planner session."""

    # purpose: score multi-enzyme compatibility for planner guardrails
    # inputs: planner record and optional enzyme overrides
    # outputs: updated planner with restriction digest payload
    # status: experimental
    profile = DEFAULT_TOOLKIT_PROFILE
    upstream_profile = (planner.primer_set or {}).get("profile") if planner.primer_set else {}
    resolved_preset = _resolve_toolkit_preset(
        planner,
        override=(preset_id or (upstream_profile or {}).get("preset_id")),
    )
    digest_payload = sequence_toolkit.analyze_restriction_digest(
        planner.input_sequences,
        config=profile,
        enzymes=enzymes,
        preset_id=resolved_preset,
    )
    toolkit_snapshot = _toolkit_snapshot_from_profile(
        digest_payload.get("profile"),
        fallback=upstream_profile or None,
    )
    guardrail_state = _merge_guardrail_state(
        planner,
        {
            "restriction": _restriction_guardrail_summary(digest_payload),
            "toolkit": toolkit_snapshot,
        },
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
    preset_id: str | None = None,
    task_id: str | None = None,
) -> models.CloningPlannerSession:
    """Execute assembly simulation for a planner session."""

    # purpose: simulate assembly junction success probabilities
    # inputs: planner record and optional strategy override
    # outputs: updated planner with assembly plan payload
    # status: experimental
    profile = DEFAULT_TOOLKIT_PROFILE
    upstream_profile = (planner.restriction_digest or {}).get("profile") if planner.restriction_digest else {}
    resolved_preset = _resolve_toolkit_preset(
        planner,
        override=(preset_id or (upstream_profile or {}).get("preset_id")),
    )
    plan_payload = sequence_toolkit.simulate_assembly(
        planner.primer_set,
        planner.restriction_digest,
        config=profile,
        strategy=strategy or planner.assembly_strategy,
        preset_id=resolved_preset,
    )
    toolkit_snapshot = _toolkit_snapshot_from_profile(
        plan_payload.get("profile"),
        fallback=upstream_profile or None,
    )
    guardrail_state = _merge_guardrail_state(
        planner,
        {
            "assembly": _assembly_guardrail_summary(plan_payload),
            "toolkit": toolkit_snapshot,
        },
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
    upstream_profile = (planner.assembly_plan or {}).get("profile") if planner.assembly_plan else {}
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
        {
            "qc": qc_summary,
            "toolkit": _toolkit_snapshot_from_profile(
                qc_payload.get("profile"),
                fallback=upstream_profile or None,
            ),
        },
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
    active_branch_id, _ = _ensure_branch_state(planner)
    previous_gate = _evaluate_guardrail_gate(planner.guardrail_state or {})
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
            "branch_id": str(active_branch_id) if active_branch_id else None,
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
    event_id = str(uuid4())
    _dispatch_planner_event(
        planner,
        "stage_started",
        {"stage": stage, "task_id": task_id},
        previous_guardrail_gate=previous_gate,
        branch_id=active_branch_id,
        checkpoint={"key": stage, "payload": entry},
        event_id=event_id,
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
    active_branch_id, _ = _ensure_branch_state(planner)
    previous_gate = _evaluate_guardrail_gate(planner.guardrail_state or {})
    timings = dict(planner.stage_timings or {})
    entry = dict(timings.get(stage) or {})
    entry.update(
        {
            "status": f"{stage}_errored",
            "error": str(exc),
            "completed_at": now.isoformat(),
            "branch_id": str(active_branch_id) if active_branch_id else None,
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
    event_id = str(uuid4())
    current_gate = _evaluate_guardrail_gate(planner.guardrail_state or {})
    record = _persist_stage_record(
        db,
        planner,
        step=stage,
        status=f"{stage}_errored",
        guardrail_snapshot={},
        payload={},
        task_id=task_id,
        error=str(exc),
        branch_id=active_branch_id,
        checkpoint_key=stage,
        checkpoint_payload=entry,
        guardrail_transition={"previous": previous_gate, "current": current_gate},
        timeline_position=event_id,
    )
    db.commit()
    _dispatch_planner_event(
        planner,
        "stage_failed",
        {"stage": stage, "error": str(exc), "record_id": str(record.id)},
        previous_guardrail_gate=previous_gate,
        branch_id=active_branch_id,
        checkpoint={"key": stage, "payload": entry},
        event_id=event_id,
    )


def _complete_pipeline_stage(
    db: Session,
    planner: models.CloningPlannerSession,
    *,
    task_id: str | None,
) -> models.CloningPlannerSession:
    """Summarise guardrail state and mark pipeline completion checkpoint."""

    active_branch_id, _ = _ensure_branch_state(planner)
    previous_gate = _evaluate_guardrail_gate(planner.guardrail_state or {})
    guardrails = refresh_planner_guardrails(db, planner)
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
            "guardrail_gate": _evaluate_guardrail_gate(guardrails),
            "error": None,
            "branch_id": str(active_branch_id) if active_branch_id else None,
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
    event_id = str(uuid4())
    current_gate = _evaluate_guardrail_gate(guardrails)
    record = _persist_stage_record(
        db,
        planner,
        step="finalize",
        status=status,
        guardrail_snapshot=guardrails,
        payload=guardrails,
        task_id=task_id,
        error=None,
        branch_id=active_branch_id,
        checkpoint_key="finalize",
        checkpoint_payload=entry,
        guardrail_transition={"previous": previous_gate, "current": current_gate},
        timeline_position=event_id,
    )
    db.flush()
    db.refresh(planner)
    _dispatch_planner_event(
        planner,
        "stage_completed",
        {"stage": "finalize", "record_id": str(record.id), "status": status},
        previous_guardrail_gate=previous_gate,
        branch_id=active_branch_id,
        checkpoint={"key": "finalize", "payload": entry},
        event_id=event_id,
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
        guardrail_snapshot = refresh_planner_guardrails(db, planner)
        gate_state = _evaluate_guardrail_gate(guardrail_snapshot)
        if gate_state.get("active"):
            _record_guardrail_hold(db, planner, stage, gate_state, task_id=task_id)
            db.commit()
            return str(planner.id)
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
    preset_id: str | None = None,
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
            preset_id=preset_id,
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
    preset_id: str | None = None,
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
            preset_id=preset_id,
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
    preset_id: str | None = None,
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
            preset_id=preset_id,
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
    preset_id: str | None = None,
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
                preset_id=preset_id,
            ),
        ),
        (
            "restriction",
            restriction_stage_task.s(
                enzymes=list(enzymes) if enzymes else None,
                preset_id=preset_id,
            ),
        ),
        (
            "assembly",
            assembly_stage_task.s(preset_id=preset_id),
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
    active_branch_id, _ = _ensure_branch_state(planner)
    previous_gate = _evaluate_guardrail_gate(planner.guardrail_state or {})
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
    state_override: dict[str, Any] | None = guardrail_state if guardrail_state is not None else None
    guardrail_snapshot = refresh_planner_guardrails(
        db,
        planner,
        base_snapshot=guardrail_snapshot,
        override=state_override,
    )
    normalised_snapshot = guardrail_snapshot
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
            "branch_id": str(active_branch_id) if active_branch_id else None,
        }
    )
    gate_state = _evaluate_guardrail_gate(guardrail_snapshot)
    checkpoint_payload["guardrail_gate"] = gate_state
    stage_guardrail: dict[str, Any] = {}
    guardrail_key = guardrail_snapshot.get(step)
    if isinstance(guardrail_key, dict):
        stage_guardrail.update(guardrail_key)
    custody_overlay = guardrail_snapshot.get("custody")
    if isinstance(custody_overlay, dict):
        stage_guardrail.setdefault("custody", custody_overlay)
        stage_guardrail["custody_status"] = guardrail_snapshot.get("custody_status")
        stage_guardrail["qc_backpressure"] = guardrail_snapshot.get("qc_backpressure")
    if stage_guardrail:
        checkpoint_payload["guardrail"] = stage_guardrail
    planner.stage_timings[step] = checkpoint_payload
    planner.updated_at = now
    if next_step:
        planner.current_step = next_step
    resolved_status = status or f"{step}_completed"
    planner.status = resolved_status
    if resolved_status in {"finalized", "completed"}:
        planner.completed_at = now
    db.add(planner)
    stage_guardrail_payload = json.loads(json.dumps(stage_guardrail, default=_json_default)) if stage_guardrail else {}
    event_id = str(uuid4())
    record = _persist_stage_record(
        db,
        planner,
        step=step,
        status=resolved_status,
        guardrail_snapshot=stage_guardrail_payload,
        payload=payload,
        task_id=task_id,
        error=error,
        branch_id=active_branch_id,
        checkpoint_key=step,
        checkpoint_payload=checkpoint_payload,
        guardrail_transition={
            "previous": previous_gate,
            "current": gate_state,
        },
        timeline_position=event_id,
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
        previous_guardrail_gate=previous_gate,
        branch_id=active_branch_id,
        checkpoint={"key": step, "payload": checkpoint_payload},
        event_id=event_id,
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
    base_snapshot = compose_guardrail_state(planner)
    active_branch_id, _ = _ensure_branch_state(planner)
    previous_gate = _evaluate_guardrail_gate(base_snapshot)
    merged_guardrails = dict(base_snapshot)
    if isinstance(guardrail_state, dict):
        merged_guardrails.update(guardrail_state)
    planner.guardrail_state = merged_guardrails
    planner.status = "finalized"
    planner.current_step = "finalized"
    planner.completed_at = now
    planner.updated_at = now
    planner.stage_timings = dict(planner.stage_timings or {})
    checkpoint_payload = {
        "status": "finalized",
        "completed_at": now.isoformat(),
        "task_id": None,
        "next_step": None,
        "error": None,
        "branch_id": str(active_branch_id) if active_branch_id else None,
        "guardrail_gate": _evaluate_guardrail_gate(merged_guardrails),
    }
    planner.stage_timings["finalize"] = checkpoint_payload
    db.add(planner)
    event_id = str(uuid4())
    current_gate = checkpoint_payload["guardrail_gate"]
    record = _persist_stage_record(
        db,
        planner,
        step="finalize",
        status="finalized",
        guardrail_snapshot=planner.guardrail_state or {},
        payload=planner.guardrail_state or {},
        task_id=None,
        error=None,
        branch_id=active_branch_id,
        checkpoint_key="finalize",
        checkpoint_payload=checkpoint_payload,
        guardrail_transition={"previous": previous_gate, "current": current_gate},
        timeline_position=event_id,
    )
    db.flush()
    db.refresh(planner)
    _dispatch_planner_event(
        planner,
        "session_finalized",
        {"stage": "finalize", "record_id": str(record.id), "status": "finalized"},
        previous_guardrail_gate=previous_gate,
        branch_id=active_branch_id,
        checkpoint={"key": "finalize", "payload": checkpoint_payload},
        event_id=event_id,
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
        "branch_id": record.branch_id,
        "checkpoint_key": record.checkpoint_key,
        "checkpoint_payload": record.checkpoint_payload,
        "guardrail_transition": record.guardrail_transition,
        "timeline_position": record.timeline_position,
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
    active_branch_id, branch_state = _ensure_branch_state(planner)
    stage_history = [
        _serialise_stage_record(record)
        for record in sorted(planner.stage_history or [], key=lambda item: item.created_at or datetime.min)
    ]
    qc_artifacts = [
        _serialise_qc_artifact(artifact)
        for artifact in sorted(planner.qc_artifacts or [], key=lambda item: item.created_at or datetime.min)
    ]
    guardrail_state = compose_guardrail_state(planner)
    primer_payload = _merge_with_defaults(
        planner.primer_set,
        {
            "primers": [],
            "summary": {
                "primer_count": 0,
                "average_tm": 0.0,
                "min_tm": 0.0,
                "max_tm": 0.0,
            },
        },
    )
    restriction_payload = _merge_with_defaults(
        planner.restriction_digest,
        {"enzymes": [], "digests": [], "alerts": []},
    )
    assembly_payload = _merge_with_defaults(
        planner.assembly_plan,
        {
            "strategy": planner.assembly_strategy,
            "steps": [],
            "average_success": 0.0,
            "min_success": 0.0,
            "max_success": 0.0,
            "payload_contract": {},
            "metadata_tags": [],
        },
    )
    qc_payload = _merge_with_defaults(planner.qc_reports, {"reports": []})
    return {
        "id": planner.id,
        "created_by_id": planner.created_by_id,
        "status": planner.status,
        "assembly_strategy": planner.assembly_strategy,
        "protocol_execution_id": planner.protocol_execution_id,
        "input_sequences": planner.input_sequences,
        "primer_set": primer_payload,
        "restriction_digest": restriction_payload,
        "assembly_plan": assembly_payload,
        "qc_reports": qc_payload,
        "inventory_reservations": planner.inventory_reservations,
        "guardrail_state": guardrail_state,
        "guardrail_gate": _evaluate_guardrail_gate(guardrail_state),
        "stage_timings": planner.stage_timings,
        "current_step": planner.current_step,
        "celery_task_id": planner.celery_task_id,
        "last_error": planner.last_error,
        "branch_state": branch_state,
        "active_branch_id": active_branch_id,
        "timeline_cursor": planner.timeline_cursor,
        "created_at": planner.created_at,
        "updated_at": planner.updated_at,
        "completed_at": planner.completed_at,
        "stage_history": stage_history,
        "qc_artifacts": qc_artifacts,
    }


def guardrail_status_snapshot(
    db: Session, planner: models.CloningPlannerSession
) -> dict[str, Any]:
    """Return a focused guardrail status payload for a planner session."""

    state = refresh_planner_guardrails(db, planner)
    gate = _evaluate_guardrail_gate(state)
    return {
        "session_id": planner.id,
        "protocol_execution_id": planner.protocol_execution_id,
        "status": planner.status,
        "guardrail_state": state,
        "guardrail_gate": gate,
        "custody_status": state.get("custody_status"),
        "qc_backpressure": state.get("qc_backpressure", False),
        "updated_at": planner.updated_at,
    }
