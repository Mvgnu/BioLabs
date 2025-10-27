"""Analytics aggregation routines for governance previews and execution outcomes."""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean
from typing import Iterable, Sequence, Set
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas

# purpose: derive leadership-ready governance analytics from preview telemetry and execution results
# inputs: SQLAlchemy session, authenticated user context, execution identifiers (optional)
# outputs: GovernanceAnalyticsReport instances powering dashboards and recommendations
# status: pilot


def _parse_iso_timestamp(value: object) -> datetime | None:
    """Return timezone-aware datetime parsed from ISO strings when possible."""

    if not isinstance(value, str):
        return None
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _coerce_uuid(value: object) -> UUID | None:
    """Best-effort coercion of arbitrary values into UUID objects."""

    try:
        candidate = UUID(str(value))
    except (TypeError, ValueError):
        return None
    return candidate


def _collect_step_completion_map(execution: models.ProtocolExecution) -> dict[int, datetime]:
    """Extract per-step completion timestamps from execution.result payloads."""

    # purpose: translate execution step telemetry into lookup map for SLA accuracy checks
    # inputs: protocol execution ORM instance containing result metadata
    # outputs: dict mapping step indexes to completion datetimes when available
    # status: pilot
    completion_map: dict[int, datetime] = {}
    result_payload = execution.result if isinstance(execution.result, dict) else {}
    steps_payload = result_payload.get("steps", {}) if isinstance(result_payload, dict) else {}
    if isinstance(steps_payload, dict):
        for key, step_data in steps_payload.items():
            try:
                step_index = int(key)
            except (TypeError, ValueError):
                continue
            if not isinstance(step_data, dict):
                continue
            completed_at = _parse_iso_timestamp(step_data.get("completed_at"))
            if completed_at is not None:
                completion_map[step_index] = completed_at
    return completion_map


def compute_governance_analytics(
    db: Session,
    user: models.User,
    team_ids: Set[UUID] | None = None,
    execution_ids: Sequence[UUID] | None = None,
    limit: int | None = 50,
) -> schemas.GovernanceAnalyticsReport:
    """Blend preview telemetry with execution history to produce analytics summaries."""

    membership_ids = set(team_ids or set())
    query = (
        db.query(models.ExecutionEvent)
        .join(
            models.ProtocolExecution,
            models.ExecutionEvent.execution_id == models.ProtocolExecution.id,
        )
        .join(models.ProtocolTemplate, models.ProtocolExecution.template_id == models.ProtocolTemplate.id)
        .filter(models.ExecutionEvent.event_type == "governance.preview.summary")
    )

    if execution_ids:
        query = query.filter(models.ExecutionEvent.execution_id.in_(execution_ids))

    if not user.is_admin:
        access_filters = [models.ProtocolExecution.run_by == user.id]
        access_filters.append(models.ProtocolTemplate.team_id.is_(None))
        if membership_ids:
            access_filters.append(models.ProtocolTemplate.team_id.in_(membership_ids))
        query = query.filter(or_(*access_filters))

    query = query.options(joinedload(models.ExecutionEvent.execution))
    query = query.order_by(
        models.ExecutionEvent.created_at.desc(),
        models.ExecutionEvent.sequence.desc(),
    )
    if limit is not None and limit > 0:
        query = query.limit(limit)

    events: Iterable[models.ExecutionEvent] = query.all()

    results: list[schemas.GovernanceAnalyticsPreviewSummary] = []
    total_new_blockers = 0
    total_resolved_blockers = 0
    blocked_ratios: list[float] = []
    sla_ratio_samples: list[float] = []

    for event in events:
        execution = event.execution
        if execution is None:
            continue
        payload = event.payload if isinstance(event.payload, dict) else {}
        stage_predictions = payload.get("stage_predictions", [])
        if not isinstance(stage_predictions, list):
            stage_predictions = []

        generated_at = _parse_iso_timestamp(payload.get("generated_at")) or event.created_at
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=timezone.utc)

        stage_count = int(payload.get("stage_count", 0) or 0)
        blocked_stage_count = int(payload.get("blocked_stage_count", 0) or 0)
        blocked_ratio = (blocked_stage_count / stage_count) if stage_count else 0.0
        overrides_applied = int(payload.get("override_count", 0) or 0)
        new_blocker_count = int(payload.get("new_blocker_count", 0) or 0)
        resolved_blocker_count = int(payload.get("resolved_blocker_count", 0) or 0)
        raw_heatmap = payload.get("blocked_stage_indexes", [])
        blocker_heatmap: list[int] = []
        if isinstance(raw_heatmap, list):
            for entry in raw_heatmap:
                try:
                    blocker_heatmap.append(int(entry))
                except (TypeError, ValueError):
                    continue

        total_new_blockers += new_blocker_count
        total_resolved_blockers += resolved_blocker_count
        blocked_ratios.append(blocked_ratio)

        step_completion_map = _collect_step_completion_map(execution)
        sla_samples: list[schemas.GovernanceAnalyticsSlaSample] = []
        sla_within_count = 0
        sla_evaluated_count = 0
        delta_minutes_collection: list[int] = []

        for stage_entry in stage_predictions:
            if not isinstance(stage_entry, dict):
                continue
            try:
                stage_index = int(stage_entry.get("index", 0) or 0)
            except (TypeError, ValueError):
                stage_index = 0
            projected_due_at = _parse_iso_timestamp(stage_entry.get("projected_due_at"))
            mapped_steps = stage_entry.get("mapped_step_indexes", [])
            mapped_indexes: list[int] = []
            if isinstance(mapped_steps, list):
                for entry in mapped_steps:
                    try:
                        mapped_indexes.append(int(entry))
                    except (TypeError, ValueError):
                        continue
            actual_candidates = [step_completion_map.get(idx) for idx in mapped_indexes]
            actual_completed_at = None
            actual_candidates = [candidate for candidate in actual_candidates if candidate is not None]
            if actual_candidates:
                actual_completed_at = max(actual_candidates)
            delta_minutes = None
            within_target = None
            if projected_due_at and actual_completed_at:
                delta_minutes = int(
                    (actual_completed_at - projected_due_at).total_seconds() // 60
                )
                within_target = delta_minutes <= 0
                sla_evaluated_count += 1
                if within_target:
                    sla_within_count += 1
                delta_minutes_collection.append(delta_minutes)
            sla_samples.append(
                schemas.GovernanceAnalyticsSlaSample(
                    stage_index=stage_index,
                    predicted_due_at=projected_due_at,
                    actual_completed_at=actual_completed_at,
                    delta_minutes=delta_minutes,
                    within_target=within_target,
                )
            )

        sla_within_ratio = None
        if sla_evaluated_count:
            sla_within_ratio = sla_within_count / sla_evaluated_count
            sla_ratio_samples.append(sla_within_ratio)

        mean_sla_delta = None
        if delta_minutes_collection:
            mean_sla_delta = mean(delta_minutes_collection)

        risk_score = blocked_ratio
        if sla_within_ratio is not None:
            risk_score += max(0.0, 1.0 - sla_within_ratio)
        if risk_score >= 1.0:
            risk_level = "high"
        elif risk_score >= 0.5:
            risk_level = "medium"
        else:
            risk_level = "low"

        ladder_load = float(stage_count + overrides_applied)

        snapshot_id = _coerce_uuid(payload.get("snapshot_id"))
        baseline_snapshot_id = _coerce_uuid(payload.get("baseline_snapshot_id"))

        results.append(
            schemas.GovernanceAnalyticsPreviewSummary(
                execution_id=execution.id,
                preview_event_id=event.id,
                snapshot_id=snapshot_id or execution.template_id,
                baseline_snapshot_id=baseline_snapshot_id,
                generated_at=generated_at,
                stage_count=stage_count,
                blocked_stage_count=blocked_stage_count,
                blocked_ratio=blocked_ratio,
                overrides_applied=overrides_applied,
                new_blocker_count=new_blocker_count,
                resolved_blocker_count=resolved_blocker_count,
                ladder_load=ladder_load,
                sla_within_target_ratio=sla_within_ratio,
                mean_sla_delta_minutes=mean_sla_delta,
                sla_samples=sla_samples,
                blocker_heatmap=blocker_heatmap,
                risk_level=risk_level,
            )
        )

    average_blocked_ratio = mean(blocked_ratios) if blocked_ratios else 0.0
    average_sla_within = mean(sla_ratio_samples) if sla_ratio_samples else None

    totals = schemas.GovernanceAnalyticsTotals(
        preview_count=len(results),
        average_blocked_ratio=average_blocked_ratio,
        total_new_blockers=total_new_blockers,
        total_resolved_blockers=total_resolved_blockers,
        average_sla_within_target_ratio=average_sla_within,
    )

    return schemas.GovernanceAnalyticsReport(results=results, totals=totals)

