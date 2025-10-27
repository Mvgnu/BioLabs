"""Analytics aggregation routines for governance previews and execution outcomes."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from math import ceil, floor
from statistics import mean
from typing import Any, Iterable, Sequence, Set
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


REVIEWER_LATENCY_BANDS: tuple[tuple[str, int | None, int | None], ...] = (
    ("under_2h", None, 120),
    ("two_to_eight_h", 120, 480),
    ("eight_to_day", 480, 1440),
    ("over_day", 1440, None),
)

REVIEWER_LOAD_RANK = {"saturated": 3, "steady": 2, "light": 1}


def _coerce_uuid(value: object) -> UUID | None:
    """Best-effort coercion of arbitrary values into UUID objects."""

    try:
        candidate = UUID(str(value))
    except (TypeError, ValueError):
        return None
    return candidate


def _normalise_minutes(value: float | int | None) -> float | None:
    """Return a non-negative minute value when provided."""

    if value is None:
        return None
    if value < 0:
        return 0.0
    return float(value)


def _classify_latency_band(minutes: float | None) -> str | None:
    """Bucket latency minutes into configured reviewer cadence bands."""

    normalised = _normalise_minutes(minutes)
    if normalised is None:
        return None
    for label, start, end in REVIEWER_LATENCY_BANDS:
        lower_bound = start if start is not None else float("-inf")
        upper_bound = end if end is not None else float("inf")
        if lower_bound <= normalised < upper_bound:
            return label
    return REVIEWER_LATENCY_BANDS[-1][0]


def _calculate_percentile(samples: Sequence[float], percentile: float) -> float | None:
    """Return percentile estimate for provided samples using linear interpolation."""

    if not samples:
        return None
    ordered = sorted(samples)
    if not ordered:
        return None
    clamped = max(0.0, min(100.0, percentile))
    if clamped == 0.0:
        return float(ordered[0])
    if clamped == 100.0:
        return float(ordered[-1])
    rank = (clamped / 100.0) * (len(ordered) - 1)
    lower_index = floor(rank)
    upper_index = ceil(rank)
    lower_value = float(ordered[lower_index])
    upper_value = float(ordered[upper_index])
    if lower_index == upper_index:
        return lower_value
    fraction = rank - lower_index
    return lower_value + (upper_value - lower_value) * fraction


def _determine_load_band(assignment_count: int, pending_count: int) -> str:
    """Classify reviewer cadence load using assignment and pending volumes."""

    if pending_count >= 8 or assignment_count >= 12:
        return "saturated"
    if pending_count >= 4 or assignment_count >= 6:
        return "steady"
    return "light"


def _build_latency_band_payload(
    counts: dict[str, int]
) -> list[schemas.GovernanceAnalyticsLatencyBand]:
    """Convert latency histogram counts into structured band payloads."""

    payload: list[schemas.GovernanceAnalyticsLatencyBand] = []
    for label, start, end in REVIEWER_LATENCY_BANDS:
        payload.append(
            schemas.GovernanceAnalyticsLatencyBand(
                label=label,
                start_minutes=start,
                end_minutes=end,
                count=counts.get(label, 0),
            )
        )
    return payload


def _calculate_publish_streak(
    published_at_values: list[datetime],
) -> tuple[int, datetime | None]:
    """Determine the contiguous publish streak (<=72h gaps) for a reviewer."""

    if not published_at_values:
        return 0, None
    ordered = sorted(
        [value for value in published_at_values if isinstance(value, datetime)]
    )
    if not ordered:
        return 0, None
    streak = 1
    last_value = ordered[-1]
    threshold_seconds = 72 * 60 * 60
    for candidate in reversed(ordered[:-1]):
        delta_seconds = (last_value - candidate).total_seconds()
        if delta_seconds <= threshold_seconds:
            streak += 1
            last_value = candidate
        else:
            break
    return streak, ordered[-1]


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
    include_previews: bool = True,
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

    query = query.options(
        joinedload(models.ExecutionEvent.execution).joinedload(
            models.ProtocolExecution.baseline_versions
        )
    )
    query = query.order_by(
        models.ExecutionEvent.created_at.desc(),
        models.ExecutionEvent.sequence.desc(),
    )
    if limit is not None and limit > 0:
        query = query.limit(limit)

    events: Iterable[models.ExecutionEvent] = query.all()

    results: list[schemas.GovernanceAnalyticsPreviewSummary] = []
    preview_count = 0
    total_new_blockers = 0
    total_resolved_blockers = 0
    total_baseline_versions = 0
    total_rollbacks = 0
    blocked_ratios: list[float] = []
    sla_ratio_samples: list[float] = []
    approval_latency_samples: list[float] = []
    publication_cadence_samples: list[float] = []

    reviewer_stats: dict[UUID, dict[str, Any]] = {}

    def _ensure_reviewer_stat(reviewer_id: UUID) -> dict[str, Any]:
        stats = reviewer_stats.get(reviewer_id)
        if stats is None:
            stats = {
                "assigned": 0,
                "completed": 0,
                "pending": 0,
                "latency_samples": [],
                "latency_band_counts": defaultdict(int),
                "blocked_samples": [],
                "churn_samples": [],
                "rollback_precursors": 0,
                "publish_dates": [],
            }
            reviewer_stats[reviewer_id] = stats
        return stats

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
        baseline_versions = list(getattr(execution, "baseline_versions", []) or [])
        total_baseline_versions += len(baseline_versions)

        baseline_approval_latencies: list[float] = []
        baseline_publication_cadence: list[float] = []
        baseline_rollback_count = 0

        published_versions = [
            baseline
            for baseline in baseline_versions
            if baseline.published_at is not None
        ]
        published_versions.sort(key=lambda baseline: baseline.published_at)

        summary_reviewer_ids: set[UUID] = set()
        for baseline in baseline_versions:
            submitted_at = baseline.submitted_at
            reviewed_at = baseline.reviewed_at
            assigned_reviewers: list[UUID] = []
            raw_reviewer_ids = (
                baseline.reviewer_ids if isinstance(baseline.reviewer_ids, list) else []
            )
            for entry in raw_reviewer_ids:
                reviewer_uuid = _coerce_uuid(entry)
                if reviewer_uuid is None:
                    continue
                assigned_reviewers.append(reviewer_uuid)
                summary_reviewer_ids.add(reviewer_uuid)
                stats = _ensure_reviewer_stat(reviewer_uuid)
                stats["assigned"] += 1
                if reviewed_at is None:
                    stats["pending"] += 1
            if submitted_at and reviewed_at:
                delta_minutes = (reviewed_at - submitted_at).total_seconds() / 60
                baseline_approval_latencies.append(delta_minutes)
            else:
                delta_minutes = None
            actual_reviewer_id = getattr(baseline, "reviewed_by_id", None)
            if actual_reviewer_id:
                summary_reviewer_ids.add(actual_reviewer_id)
                stats = _ensure_reviewer_stat(actual_reviewer_id)
                if actual_reviewer_id not in assigned_reviewers:
                    stats["assigned"] += 1
                stats["completed"] += 1
                normalised_latency = _normalise_minutes(delta_minutes)
                if normalised_latency is not None:
                    stats["latency_samples"].append(normalised_latency)
                    band_label = _classify_latency_band(normalised_latency)
                    if band_label:
                        stats["latency_band_counts"][band_label] += 1
                if baseline.status == "rolled_back" or baseline.rolled_back_at is not None:
                    stats["rollback_precursors"] += 1
            publisher_id = getattr(baseline, "published_by_id", None)
            if publisher_id:
                summary_reviewer_ids.add(publisher_id)
                stats = _ensure_reviewer_stat(publisher_id)
                if publisher_id not in assigned_reviewers and publisher_id != actual_reviewer_id:
                    stats["assigned"] += 1
                publish_at = getattr(baseline, "published_at", None)
                if isinstance(publish_at, datetime):
                    stats["publish_dates"].append(publish_at)
            if baseline.status == "rolled_back" or baseline.rolled_back_at is not None:
                baseline_rollback_count += 1

        if len(published_versions) >= 2:
            for previous, current in zip(published_versions, published_versions[1:]):
                if previous.published_at and current.published_at:
                    cadence_days = (
                        current.published_at - previous.published_at
                    ).total_seconds() / (60 * 60 * 24)
                    baseline_publication_cadence.append(cadence_days)

        approval_latency_value = (
            mean(baseline_approval_latencies)
            if baseline_approval_latencies
            else None
        )
        publication_cadence_value = (
            mean(baseline_publication_cadence)
            if baseline_publication_cadence
            else None
        )

        if approval_latency_value is not None:
            approval_latency_samples.append(approval_latency_value)
        if publication_cadence_value is not None:
            publication_cadence_samples.append(publication_cadence_value)
        total_rollbacks += baseline_rollback_count
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

        summary_churn_index = blocked_ratio * float(
            len(baseline_versions) + baseline_rollback_count
        )

        for reviewer_id in summary_reviewer_ids:
            stats = _ensure_reviewer_stat(reviewer_id)
            stats["blocked_samples"].append(blocked_ratio)
            stats["churn_samples"].append(len(baseline_versions) + baseline_rollback_count)

        preview_count += 1
        if include_previews:
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
                    baseline_version_count=len(baseline_versions),
                    approval_latency_minutes=approval_latency_value,
                    publication_cadence_days=publication_cadence_value,
                    rollback_count=baseline_rollback_count,
                    blocker_churn_index=summary_churn_index,
                )
            )

    average_blocked_ratio = mean(blocked_ratios) if blocked_ratios else 0.0
    average_sla_within = mean(sla_ratio_samples) if sla_ratio_samples else None

    average_approval_latency = (
        mean(approval_latency_samples) if approval_latency_samples else None
    )
    average_publication_cadence = (
        mean(publication_cadence_samples)
        if publication_cadence_samples
        else None
    )

    reviewer_cadence: list[schemas.GovernanceReviewerCadenceSummary] = []
    streak_alert_count = 0
    if reviewer_stats:
        reviewer_ids = list(reviewer_stats.keys())
        reviewer_users = {
            user.id: user
            for user in db.query(models.User)
            .filter(models.User.id.in_(reviewer_ids))
            .all()
        }

        allowed_reviewer_ids: set[UUID]
        if user.is_admin or not membership_ids:
            allowed_reviewer_ids = set(reviewer_ids)
        else:
            allowed_reviewer_ids = {
                membership.user_id
                for membership in db.query(models.TeamMember)
                .filter(models.TeamMember.team_id.in_(list(membership_ids)))
                .all()
            }
            allowed_reviewer_ids.add(user.id)

        for reviewer_id, stats in reviewer_stats.items():
            if reviewer_id not in allowed_reviewer_ids:
                continue
            user = reviewer_users.get(reviewer_id)
            latency_samples: list[float] = stats["latency_samples"]
            average_latency = (
                mean(latency_samples) if latency_samples else None
            )
            latency_payload = _build_latency_band_payload(
                dict(stats["latency_band_counts"])
            )
            blocked_ratio_sample = (
                mean(stats["blocked_samples"])
                if stats["blocked_samples"]
                else None
            )
            churn_sample = (
                mean(stats["churn_samples"])
                if stats["churn_samples"]
                else None
            )
            streak, last_publish = _calculate_publish_streak(stats["publish_dates"])
            streak_alert = streak >= 3
            if streak_alert:
                streak_alert_count += 1
            reviewer_cadence.append(
                schemas.GovernanceReviewerCadenceSummary(
                    reviewer_id=reviewer_id,
                    reviewer_email=getattr(user, "email", None),
                    reviewer_name=getattr(user, "full_name", None),
                    assignment_count=stats["assigned"],
                    completion_count=stats["completed"],
                    pending_count=stats["pending"],
                    load_band=_determine_load_band(
                        stats["assigned"], stats["pending"]
                    ),
                    average_latency_minutes=average_latency,
                    latency_p50_minutes=_calculate_percentile(
                        latency_samples, 50.0
                    ),
                    latency_p90_minutes=_calculate_percentile(
                        latency_samples, 90.0
                    ),
                    latency_bands=latency_payload,
                    blocked_ratio_trailing=blocked_ratio_sample,
                    churn_signal=churn_sample,
                    rollback_precursor_count=stats["rollback_precursors"],
                    publish_streak=streak,
                    last_publish_at=last_publish,
                    streak_alert=streak_alert,
                )
            )

    reviewer_cadence.sort(
        key=lambda item: (
            REVIEWER_LOAD_RANK.get(item.load_band, 0),
            item.completion_count,
        ),
        reverse=True,
    )

    totals = schemas.GovernanceAnalyticsTotals(
        preview_count=preview_count,
        average_blocked_ratio=average_blocked_ratio,
        total_new_blockers=total_new_blockers,
        total_resolved_blockers=total_resolved_blockers,
        average_sla_within_target_ratio=average_sla_within,
        total_baseline_versions=total_baseline_versions,
        total_rollbacks=total_rollbacks,
        average_approval_latency_minutes=average_approval_latency,
        average_publication_cadence_days=average_publication_cadence,
        reviewer_count=len(reviewer_cadence),
        streak_alert_count=streak_alert_count,
    )

    return schemas.GovernanceAnalyticsReport(
        results=results, reviewer_cadence=reviewer_cadence, totals=totals
    )

