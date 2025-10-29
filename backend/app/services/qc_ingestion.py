"""Chromatogram and QC artifact ingestion helpers."""

from __future__ import annotations

from __future__ import annotations
from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime, timezone
from statistics import mean
from typing import Any

from sqlalchemy.orm import Session

from .. import models, storage


def _normalise_signal(trace: Sequence[float]) -> list[float]:
    """Return baseline-corrected trace intensities."""

    # purpose: remove baseline offset before downstream QC heuristics
    if not trace:
        return []
    baseline = min(trace)
    return [value - baseline for value in trace]


def _signal_to_noise(trace: Sequence[float]) -> float:
    """Compute signal-to-noise ratio for a chromatogram trace."""

    # purpose: derive QC guardrail heuristics from chromatogram intensity profiles
    normalised = _normalise_signal(trace)
    if not normalised:
        return 0.0
    peak = max(normalised)
    noise_window = normalised[: len(normalised) // 10 or 1]
    noise = mean(noise_window) if noise_window else 0.0
    if noise <= 0:
        return float("inf") if peak > 0 else 0.0
    return peak / noise


def ingest_chromatograms(
    db: Session,
    planner: models.CloningPlannerSession,
    chromatograms: Sequence[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Normalise chromatogram metadata, persist artifacts, and compute guardrail heuristics."""

    # purpose: prepare QC artifacts for cloning planner guardrail gating while persisting raw signals
    # inputs: database session, planner row, optional chromatogram descriptors
    # outputs: dict containing normalised artifacts, guardrail breaches, and persisted ORM artifacts
    # status: experimental
    normalised: list[dict[str, Any]] = []
    guardrail_breaches: list[str] = []
    records: list[models.CloningPlannerQCArtifact] = []
    thresholds = {
        "min_signal_to_noise": 15.0,
        "min_trace_length": 50,
    }
    now = datetime.now(timezone.utc)
    for entry in chromatograms or []:
        trace = entry.get("trace") or []
        snr = _signal_to_noise(trace)
        metadata = entry.get("metadata", {})
        normalised_payload = {
            "name": entry.get("name"),
            "sample_id": entry.get("sample_id"),
            "signal_to_noise": snr,
            "length": len(trace),
            "metadata": metadata,
        }
        normalised.append(normalised_payload)
        trace_path = _persist_trace_payload(planner.id, entry)
        record = models.CloningPlannerQCArtifact(
            session=planner,
            artifact_name=entry.get("name"),
            sample_id=entry.get("sample_id"),
            trace_path=trace_path,
            storage_path=None,
            metrics={
                "signal_to_noise": snr,
                "length": len(trace),
                "metadata": metadata,
            },
            thresholds=thresholds,
            created_at=now,
            updated_at=now,
        )
        db.add(record)
        records.append(record)
        if snr and snr < thresholds["min_signal_to_noise"]:
            guardrail_breaches.append(
                f"Chromatogram {entry.get('name') or entry.get('sample_id') or '#'} has low SNR ({snr:.1f})"
            )
        if len(trace) < thresholds["min_trace_length"]:
            guardrail_breaches.append(
                f"Chromatogram {entry.get('name') or entry.get('sample_id') or '#'} trace too short ({len(trace)} pts)"
            )
    return {
        "artifacts": normalised,
        "breaches": guardrail_breaches,
        "records": records,
        "thresholds": thresholds,
    }


def attach_artifacts_to_stage(
    db: Session,
    artifacts: Sequence[models.CloningPlannerQCArtifact],
    stage_record: models.CloningPlannerStageRecord,
) -> None:
    """Link persisted QC artifacts with a specific planner stage record."""

    # purpose: enrich QC artifact lineage with checkpoint references
    # inputs: db session, iterable of QC artifacts, stage record row
    # status: experimental
    now = datetime.now(timezone.utc)
    for artifact in artifacts:
        artifact.stage_record = stage_record
        artifact.updated_at = now
        db.add(artifact)


def record_reviewer_decision(
    db: Session,
    artifact: models.CloningPlannerQCArtifact,
    *,
    reviewer: models.User,
    decision: str,
    notes: str | None = None,
) -> models.CloningPlannerQCArtifact:
    """Persist reviewer oversight decisions for QC artifacts."""

    # purpose: support guardrail reviewer loops for QC artifacts tied to planner sessions
    # inputs: db session, qc artifact row, reviewer user, decision string, optional notes
    # outputs: updated artifact with reviewer metadata
    # status: experimental
    now = datetime.now(timezone.utc)
    artifact.reviewer = reviewer
    artifact.reviewer_decision = decision
    artifact.reviewer_notes = notes
    artifact.reviewed_at = now
    artifact.updated_at = now
    db.add(artifact)
    return artifact


def _persist_trace_payload(planner_id, entry: dict[str, Any]) -> str | None:
    """Persist raw chromatogram trace data for later review."""

    # purpose: store raw chromatogram traces in durable storage for reviewer access
    # inputs: planner identifier, raw chromatogram payload dict
    # outputs: storage locator string or None when no trace present
    # status: experimental
    trace = entry.get("trace")
    if not trace:
        return None
    payload = {
        "name": entry.get("name"),
        "sample_id": entry.get("sample_id"),
        "metadata": entry.get("metadata", {}),
        "trace": trace,
    }
    data = json.dumps(payload).encode("utf-8")
    path, _ = storage.save_binary_payload(
        data,
        "chromatogram.json",
        namespace=f"cloning_planner/{planner_id}/qc",
        content_type="application/json",
    )
    return path
