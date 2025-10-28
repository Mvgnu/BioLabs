"""Analytics aggregation routines for governance previews and execution outcomes."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import mean
from threading import Lock
from typing import Any, Iterable, Sequence, Set
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from .reviewer import (
    REVIEWER_LATENCY_BANDS,
    ReviewerCadenceAccumulator,
    build_reviewer_cadence_report,
    ensure_reviewer_stat,
)

# purpose: derive leadership-ready governance analytics from preview telemetry and execution results
# inputs: SQLAlchemy session, authenticated user context, execution identifiers (optional)
# outputs: GovernanceAnalyticsReport instances powering dashboards and recommendations
# status: pilot

_CACHE_TTL_SECONDS = 30


@dataclass(frozen=True)
class _GovernanceAnalyticsCacheKey:
    """Immutable cache key representing analytics query scope."""

    # purpose: uniquely identify governance analytics cache entries by RBAC context
    # inputs: requesting user id/admin flag, membership scope, execution scope, pagination, preview flag
    # outputs: deterministic key for in-process cache dictionary lookups
    # status: pilot

    user_id: UUID
    is_admin: bool
    membership_scope: tuple[str, ...]
    execution_scope: tuple[str, ...]
    limit: int | None
    include_previews: bool


@dataclass
class _GovernanceAnalyticsCacheEntry:
    """Stored governance analytics payload with expiry metadata."""

    # purpose: retain analytics response snapshots until invalidation or TTL expiry
    # inputs: deep-copied analytics payload, expiry timestamp, execution scope for invalidation matching
    # outputs: reusable payload when cache hit conditions are satisfied
    # status: pilot

    payload: schemas.GovernanceAnalyticsReport
    expires_at: datetime
    execution_scope: frozenset[UUID]


_GOVERNANCE_ANALYTICS_CACHE: dict[
    _GovernanceAnalyticsCacheKey, _GovernanceAnalyticsCacheEntry
] = {}
_CACHE_LOCK = Lock()


def _normalise_uuid_tuple(values: Iterable[UUID | str | None]) -> tuple[str, ...]:
    """Return a sorted tuple of UUID strings ignoring null entries."""

    return tuple(
        sorted(
            str(UUID(str(value)))
            for value in values
            if value is not None
        )
    )


def _build_cache_key(
    *,
    user: models.User,
    membership_ids: Set[UUID],
    execution_ids: Sequence[UUID] | None,
    limit: int | None,
    include_previews: bool,
) -> _GovernanceAnalyticsCacheKey:
    """Construct a cache key for the supplied analytics parameters."""

    membership_scope = _normalise_uuid_tuple(membership_ids)
    execution_scope = _normalise_uuid_tuple(execution_ids or [])
    return _GovernanceAnalyticsCacheKey(
        user_id=user.id,
        is_admin=bool(user.is_admin),
        membership_scope=membership_scope,
        execution_scope=execution_scope,
        limit=limit,
        include_previews=include_previews,
    )


def _prune_expired_cache_entries(now: datetime | None = None) -> None:
    """Drop expired cache entries using supplied or current timestamp."""

    reference = now or datetime.now(timezone.utc)
    expired_keys = [
        cache_key
        for cache_key, entry in _GOVERNANCE_ANALYTICS_CACHE.items()
        if entry.expires_at <= reference
    ]
    for cache_key in expired_keys:
        _GOVERNANCE_ANALYTICS_CACHE.pop(cache_key, None)


def _get_cached_governance_report(
    cache_key: _GovernanceAnalyticsCacheKey,
) -> schemas.GovernanceAnalyticsReport | None:
    """Return cached analytics payload when available and fresh."""

    now = datetime.now(timezone.utc)
    with _CACHE_LOCK:
        _prune_expired_cache_entries(now)
        entry = _GOVERNANCE_ANALYTICS_CACHE.get(cache_key)
        if entry is None:
            return None
        return entry.payload.model_copy(deep=True)


def _store_governance_report_cache_entry(
    cache_key: _GovernanceAnalyticsCacheKey,
    payload: schemas.GovernanceAnalyticsReport,
    execution_scope: Iterable[UUID],
) -> None:
    """Persist analytics payload in cache with derived execution scope."""

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=_CACHE_TTL_SECONDS)
    entry = _GovernanceAnalyticsCacheEntry(
        payload=payload.model_copy(deep=True),
        expires_at=expires_at,
        execution_scope=frozenset(execution_scope),
    )
    with _CACHE_LOCK:
        _prune_expired_cache_entries(expires_at)
        _GOVERNANCE_ANALYTICS_CACHE[cache_key] = entry


def _collect_stage_metrics(export: models.ExecutionNarrativeExport) -> dict[str, int]:
    """Return counts of approval stages grouped by status."""

    metrics: dict[str, int] = {"total": export.approval_stage_count or 0}
    for stage in export.approval_stages:
        metrics[stage.status] = metrics.get(stage.status, 0) + 1
    return metrics


def _include_stage_metrics(
    report: schemas.GovernanceAnalyticsReport,
    exports: Iterable[models.ExecutionNarrativeExport],
) -> None:
    """Attach stage metrics to analytics meta payload."""

    stage_metrics = dict(report.meta.get("approval_stage_metrics", {}))
    for export in exports:
        stage_metrics[str(export.id)] = _collect_stage_metrics(export)
    report.meta["approval_stage_metrics"] = stage_metrics


def invalidate_governance_analytics_cache(
    execution_ids: Iterable[UUID | str] | None = None,
) -> None:
    """Invalidate cached governance analytics payloads for supplied executions."""

    targets: set[UUID] = set()
    if execution_ids is not None:
        for value in execution_ids:
            try:
                targets.add(UUID(str(value)))
            except (TypeError, ValueError):  # pragma: no cover - defensive guard
                continue

    now = datetime.now(timezone.utc)
    with _CACHE_LOCK:
        _prune_expired_cache_entries(now)
        if execution_ids is None:
            _GOVERNANCE_ANALYTICS_CACHE.clear()
            return
        if not targets:
            return
        keys_to_remove = [
            cache_key
            for cache_key, entry in _GOVERNANCE_ANALYTICS_CACHE.items()
            if entry.execution_scope.intersection(targets)
        ]
        for cache_key in keys_to_remove:
            _GOVERNANCE_ANALYTICS_CACHE.pop(cache_key, None)


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


def _normalise_uuid_set(values: Iterable[object]) -> set[UUID]:
    """Return a UUID set derived from arbitrary iterable values."""

    # purpose: coerce override detail reviewer lists into deterministic UUID sets
    # inputs: iterable of string/UUID-like entries extracted from override payloads
    # outputs: hashable UUID set for comparison and cadence adjustments
    # status: pilot

    result: set[UUID] = set()
    for entry in values:
        candidate = _coerce_uuid(entry)
        if candidate is not None:
            result.add(candidate)
    return result


def _extract_lineage_context(detail: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return scenario and notebook lineage payloads from override detail."""

    # purpose: reuse lineage parsing logic for analytics aggregation buckets
    # inputs: override detail payload recorded with execution events
    # outputs: tuple of (scenario_payload, notebook_payload)
    # status: pilot

    if not isinstance(detail, dict):
        return {}, {}

    lineage_payload = detail.get("lineage") if isinstance(detail.get("lineage"), dict) else {}
    scenario_payload: dict[str, Any] = {}
    notebook_payload: dict[str, Any] = {}

    if isinstance(lineage_payload, dict):
        if isinstance(lineage_payload.get("scenario"), dict):
            scenario_payload = dict(lineage_payload["scenario"])
        if isinstance(lineage_payload.get("notebook_entry"), dict):
            notebook_payload = dict(lineage_payload["notebook_entry"])

    if not scenario_payload and isinstance(detail.get("scenario"), dict):
        scenario_payload = dict(detail["scenario"])
    if not notebook_payload and isinstance(detail.get("notebook_entry"), dict):
        notebook_payload = dict(detail["notebook_entry"])

    return scenario_payload, notebook_payload


def _load_override_events(
    db: Session,
    user: models.User,
    membership_ids: Set[UUID],
    execution_ids: set[UUID],
) -> dict[UUID, list[models.ExecutionEvent]]:
    """Return override action events grouped by execution within RBAC scope."""

    # purpose: hydrate governance override actions for analytics reconciliation
    # inputs: SQLAlchemy session, authenticated user, membership scope, execution ids
    # outputs: mapping of execution id -> ordered override action events
    # status: pilot

    if not execution_ids:
        return {}

    query = (
        db.query(models.ExecutionEvent)
        .join(
            models.ProtocolExecution,
            models.ExecutionEvent.execution_id == models.ProtocolExecution.id,
        )
        .join(
            models.ProtocolTemplate,
            models.ProtocolExecution.template_id == models.ProtocolTemplate.id,
        )
        .filter(models.ExecutionEvent.event_type == "governance.override.action")
        .filter(models.ExecutionEvent.execution_id.in_(list(execution_ids)))
    )

    if not user.is_admin:
        access_filters = [models.ProtocolExecution.run_by == user.id]
        access_filters.append(models.ProtocolTemplate.team_id.is_(None))
        if membership_ids:
            access_filters.append(models.ProtocolTemplate.team_id.in_(membership_ids))
        query = query.filter(or_(*access_filters))

    query = query.order_by(
        models.ExecutionEvent.execution_id,
        models.ExecutionEvent.created_at.asc(),
        models.ExecutionEvent.sequence.asc(),
    )

    grouped: dict[UUID, list[models.ExecutionEvent]] = defaultdict(list)
    for event in query.all():
        if event.execution_id is None:
            continue
        grouped[event.execution_id].append(event)
    return grouped


def _apply_reassign_override_effect(
    detail: dict[str, Any],
    status: str,
    reviewer_stats: dict[UUID, ReviewerCadenceAccumulator],
    baseline_assignments: dict[UUID, set[UUID]],
    baseline_pending: dict[UUID, bool],
) -> float:
    """Reconcile reviewer assignment deltas stemming from override reassignments."""

    # purpose: translate override reassign/reversal payloads into reviewer cadence deltas
    # inputs: override detail payload, action status, cadence accumulators, cached baseline maps
    # outputs: ladder load delta reflecting assignment additions/removals
    # status: pilot

    baseline_uuid = _coerce_uuid(detail.get("baseline_id") or detail.get("baselineId"))
    if baseline_uuid is None:
        return 0.0

    before_values = detail.get("reviewer_ids_before") or []
    after_values = detail.get("reviewer_ids_after") or []
    if not isinstance(before_values, Iterable) or not isinstance(after_values, Iterable):
        return 0.0

    current_assignments = baseline_assignments.get(baseline_uuid)
    before_set = _normalise_uuid_set(before_values)
    after_set = _normalise_uuid_set(after_values)
    if current_assignments is None:
        current_assignments = before_set

    desired_set = after_set
    additions = desired_set - current_assignments
    removals = current_assignments - desired_set

    pending = baseline_pending.get(baseline_uuid, True)
    for reviewer_id in additions:
        accumulator = ensure_reviewer_stat(reviewer_stats, reviewer_id)
        accumulator.assigned += 1
        if pending:
            accumulator.pending += 1
    for reviewer_id in removals:
        accumulator = ensure_reviewer_stat(reviewer_stats, reviewer_id)
        if accumulator.assigned > 0:
            accumulator.assigned -= 1
        if pending and accumulator.pending > 0:
            accumulator.pending -= 1

    baseline_assignments[baseline_uuid] = desired_set
    return float(len(additions) - len(removals))


def _summarize_override_events(
    events: Sequence[models.ExecutionEvent],
    reviewer_stats: dict[UUID, ReviewerCadenceAccumulator],
    baseline_assignments: dict[UUID, set[UUID]],
    baseline_pending: dict[UUID, bool],
) -> dict[str, Any]:
    """Aggregate override deltas impacting ladder load, SLA ratios, and cadence stats."""

    # purpose: consolidate override action impacts into analytics adjustments
    # inputs: execution-scoped override events, cadence accumulators, baseline lookup tables
    # outputs: summary dict with ladder delta, SLA adjustments, and override counts
    # status: pilot

    summary = {
        "executed_count": 0,
        "reversed_count": 0,
        "ladder_delta": 0.0,
        "sla_within_adjustment": 0,
        "sla_total_adjustment": 0,
        "cooldown_delta_samples": [],
        "cooldown_minutes_net": 0.0,
    }

    scenario_buckets: dict[
        tuple[UUID | None, str | None, str | None], dict[str, Any]
    ] = {}
    notebook_buckets: dict[
        tuple[UUID | None, str | None], dict[str, Any]
    ] = {}

    for event in events:
        payload = event.payload if isinstance(event.payload, dict) else {}
        status = str(payload.get("status") or "").lower()
        action = payload.get("action")
        detail = payload.get("detail")
        if not isinstance(detail, dict) or action not in {"reassign", "cooldown", "escalate"}:
            continue
        if status not in {"executed", "reversed"}:
            continue

        if status == "executed":
            summary["executed_count"] += 1
        else:
            summary["reversed_count"] += 1

        scenario_payload, notebook_payload = _extract_lineage_context(detail)
        scenario_id = _coerce_uuid(scenario_payload.get("id"))
        scenario_name = scenario_payload.get("name")
        folder_name = scenario_payload.get("folder_name")
        scenario_key = (scenario_id, scenario_name, folder_name)
        if any(value is not None for value in scenario_key):
            bucket = scenario_buckets.setdefault(
                scenario_key,
                {
                    "scenario_id": scenario_id,
                    "scenario_name": scenario_name,
                    "folder_name": folder_name,
                    "executed_count": 0,
                    "reversed_count": 0,
                },
            )
            bucket_key = "executed_count" if status == "executed" else "reversed_count"
            bucket[bucket_key] += 1

        notebook_id = _coerce_uuid(notebook_payload.get("id"))
        notebook_title = notebook_payload.get("title")
        notebook_execution_id = _coerce_uuid(notebook_payload.get("execution_id"))
        notebook_key = (notebook_id, notebook_title)
        if any(value is not None for value in notebook_key):
            nb_bucket = notebook_buckets.setdefault(
                notebook_key,
                {
                    "notebook_entry_id": notebook_id,
                    "notebook_title": notebook_title,
                    "execution_id": notebook_execution_id,
                    "executed_count": 0,
                    "reversed_count": 0,
                },
            )
            nb_key = "executed_count" if status == "executed" else "reversed_count"
            nb_bucket[nb_key] += 1

        if action == "reassign":
            delta = _apply_reassign_override_effect(
                detail,
                status,
                reviewer_stats,
                baseline_assignments,
                baseline_pending,
            )
            summary["ladder_delta"] += delta
        elif action == "cooldown":
            raw_minutes = detail.get("cooldown_minutes")
            minutes_value = None
            try:
                if raw_minutes is not None:
                    minutes_value = float(raw_minutes)
            except (TypeError, ValueError):
                minutes_value = None
            if status == "executed":
                summary["ladder_delta"] -= 1.0
                summary["sla_within_adjustment"] += 1
                summary["sla_total_adjustment"] += 1
                if minutes_value is not None:
                    summary["cooldown_delta_samples"].append(-minutes_value)
                    summary["cooldown_minutes_net"] += minutes_value
            else:
                summary["ladder_delta"] += 1.0
                summary["sla_within_adjustment"] -= 1
                summary["sla_total_adjustment"] -= 1
                if minutes_value is not None:
                    summary["cooldown_delta_samples"].append(minutes_value)
                    summary["cooldown_minutes_net"] -= minutes_value
        elif action == "escalate":
            if status == "executed":
                summary["ladder_delta"] += 0.5
            else:
                summary["ladder_delta"] -= 0.5

    summary["scenario_buckets"] = [
        {
            **bucket,
            "net_count": bucket["executed_count"] - bucket["reversed_count"],
        }
        for bucket in scenario_buckets.values()
    ]
    summary["notebook_buckets"] = [
        {
            **bucket,
            "net_count": bucket["executed_count"] - bucket["reversed_count"],
        }
        for bucket in notebook_buckets.values()
    ]

    return summary


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
    cache_key = _build_cache_key(
        user=user,
        membership_ids=membership_ids,
        execution_ids=execution_ids,
        limit=limit,
        include_previews=include_previews,
    )
    cached_report = _get_cached_governance_report(cache_key)
    if cached_report is not None:
        return cached_report

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

    events: list[models.ExecutionEvent] = query.all()

    execution_scope_ids: set[UUID] = {
        event.execution_id
        for event in events
        if getattr(event, "execution_id", None) is not None
    }
    override_events_by_execution = _load_override_events(
        db, user, membership_ids, execution_scope_ids
    )

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

    reviewer_stats: dict[UUID, ReviewerCadenceAccumulator] = {}
    scenario_totals: dict[
        tuple[UUID | None, str | None, str | None], dict[str, Any]
    ] = {}
    notebook_totals: dict[tuple[UUID | None, str | None], dict[str, Any]] = {}

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
        baseline_assignments_map: dict[UUID, set[UUID]] = {}
        baseline_pending_map: dict[UUID, bool] = {}

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
                accumulator = ensure_reviewer_stat(
                    reviewer_stats, reviewer_uuid
                )
                accumulator.assigned += 1
                if reviewed_at is None:
                    accumulator.pending += 1
            if submitted_at and reviewed_at:
                delta_minutes = (reviewed_at - submitted_at).total_seconds() / 60
                baseline_approval_latencies.append(delta_minutes)
            else:
                delta_minutes = None
            actual_reviewer_id = getattr(baseline, "reviewed_by_id", None)
            if actual_reviewer_id:
                summary_reviewer_ids.add(actual_reviewer_id)
                accumulator = ensure_reviewer_stat(
                    reviewer_stats, actual_reviewer_id
                )
                if actual_reviewer_id not in assigned_reviewers:
                    accumulator.assigned += 1
                accumulator.completed += 1
                normalised_latency = _normalise_minutes(delta_minutes)
                if normalised_latency is not None:
                    accumulator.latency_samples.append(normalised_latency)
                    band_label = _classify_latency_band(normalised_latency)
                    if band_label:
                        accumulator.latency_band_counts[band_label] += 1
                if baseline.status == "rolled_back" or baseline.rolled_back_at is not None:
                    accumulator.rollback_precursors += 1
            publisher_id = getattr(baseline, "published_by_id", None)
            if publisher_id:
                summary_reviewer_ids.add(publisher_id)
                accumulator = ensure_reviewer_stat(
                    reviewer_stats, publisher_id
                )
                if (
                    publisher_id not in assigned_reviewers
                    and publisher_id != actual_reviewer_id
                ):
                    accumulator.assigned += 1
                publish_at = getattr(baseline, "published_at", None)
                if isinstance(publish_at, datetime):
                    accumulator.publish_dates.append(publish_at)
            if baseline.status == "rolled_back" or baseline.rolled_back_at is not None:
                baseline_rollback_count += 1

            baseline_id = getattr(baseline, "id", None)
            if isinstance(baseline_id, UUID):
                baseline_assignments_map[baseline_id] = set(assigned_reviewers)
                baseline_pending_map[baseline_id] = reviewed_at is None

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

        overrides_for_execution = override_events_by_execution.get(execution.id, [])
        override_summary = _summarize_override_events(
            overrides_for_execution,
            reviewer_stats,
            baseline_assignments_map,
            baseline_pending_map,
        )

        adjusted_within = sla_within_count + override_summary["sla_within_adjustment"]
        adjusted_total = sla_evaluated_count + override_summary["sla_total_adjustment"]
        if adjusted_within < 0:
            adjusted_within = 0
        if adjusted_total < 0:
            adjusted_total = 0

        combined_delta_samples: list[float] = [
            float(value) for value in delta_minutes_collection
        ]
        combined_delta_samples.extend(
            float(value) for value in override_summary["cooldown_delta_samples"]
        )

        sla_within_ratio = None
        if adjusted_total:
            sla_within_ratio = adjusted_within / adjusted_total
            sla_ratio_samples.append(sla_within_ratio)

        mean_sla_delta = None
        if combined_delta_samples:
            mean_sla_delta = mean(combined_delta_samples)

        risk_score = blocked_ratio
        if sla_within_ratio is not None:
            risk_score += max(0.0, 1.0 - sla_within_ratio)
        if risk_score >= 1.0:
            risk_level = "high"
        elif risk_score >= 0.5:
            risk_level = "medium"
        else:
            risk_level = "low"

        ladder_load = float(
            stage_count + overrides_applied + override_summary["ladder_delta"]
        )

        snapshot_id = _coerce_uuid(payload.get("snapshot_id"))
        baseline_snapshot_id = _coerce_uuid(payload.get("baseline_snapshot_id"))

        summary_churn_index = blocked_ratio * float(
            len(baseline_versions) + baseline_rollback_count
        )

        for reviewer_id in summary_reviewer_ids:
            accumulator = ensure_reviewer_stat(reviewer_stats, reviewer_id)
            accumulator.blocked_samples.append(blocked_ratio)
            accumulator.churn_samples.append(
                len(baseline_versions) + baseline_rollback_count
            )

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
                    override_actions_executed=override_summary["executed_count"],
                    override_actions_reversed=override_summary["reversed_count"],
                    override_cooldown_minutes=(
                        None
                        if abs(override_summary["cooldown_minutes_net"]) < 1e-6
                        else float(override_summary["cooldown_minutes_net"])
                    ),
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

        for bucket in override_summary.get("scenario_buckets", []):
            key = (
                _coerce_uuid(bucket.get("scenario_id")),
                bucket.get("scenario_name"),
                bucket.get("folder_name"),
            )
            aggregate = scenario_totals.setdefault(
                key,
                {
                    "scenario_id": key[0],
                    "scenario_name": key[1],
                    "folder_name": key[2],
                    "executed_count": 0,
                    "reversed_count": 0,
                },
            )
            aggregate["executed_count"] += int(bucket.get("executed_count", 0) or 0)
            aggregate["reversed_count"] += int(bucket.get("reversed_count", 0) or 0)

        for bucket in override_summary.get("notebook_buckets", []):
            key = (
                _coerce_uuid(bucket.get("notebook_entry_id")),
                bucket.get("notebook_title"),
            )
            aggregate = notebook_totals.setdefault(
                key,
                {
                    "notebook_entry_id": key[0],
                    "notebook_title": key[1],
                    "execution_id": _coerce_uuid(bucket.get("execution_id")),
                    "executed_count": 0,
                    "reversed_count": 0,
                },
            )
            aggregate["executed_count"] += int(bucket.get("executed_count", 0) or 0)
            aggregate["reversed_count"] += int(bucket.get("reversed_count", 0) or 0)

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

    reviewer_cadence_report = build_reviewer_cadence_report(
        db, reviewer_stats, user, membership_ids
    )
    reviewer_cadence = reviewer_cadence_report.reviewers
    cadence_totals = reviewer_cadence_report.totals

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
        reviewer_count=cadence_totals.reviewer_count,
        streak_alert_count=cadence_totals.streak_alert_count,
        reviewer_latency_p50_minutes=cadence_totals.reviewer_latency_p50_minutes,
        reviewer_latency_p90_minutes=cadence_totals.reviewer_latency_p90_minutes,
        reviewer_load_band_counts=cadence_totals.load_band_counts,
    )

    lineage_summary = schemas.GovernanceOverrideLineageAggregates(
        scenarios=[
            schemas.GovernanceScenarioOverrideAggregate(
                scenario_id=item.get("scenario_id"),
                scenario_name=item.get("scenario_name"),
                folder_name=item.get("folder_name"),
                executed_count=item.get("executed_count", 0),
                reversed_count=item.get("reversed_count", 0),
                net_count=(
                    item.get("executed_count", 0) - item.get("reversed_count", 0)
                ),
            )
            for item in scenario_totals.values()
        ],
        notebooks=[
            schemas.GovernanceNotebookOverrideAggregate(
                notebook_entry_id=item.get("notebook_entry_id"),
                notebook_title=item.get("notebook_title"),
                execution_id=item.get("execution_id"),
                executed_count=item.get("executed_count", 0),
                reversed_count=item.get("reversed_count", 0),
                net_count=(
                    item.get("executed_count", 0) - item.get("reversed_count", 0)
                ),
            )
            for item in notebook_totals.values()
        ],
    )

    report = schemas.GovernanceAnalyticsReport(
        results=results,
        reviewer_cadence=reviewer_cadence,
        totals=totals,
        lineage_summary=lineage_summary,
    )

    cache_scope_ids = set(execution_scope_ids)
    if execution_ids:
        cache_scope_ids.update(execution_ids)
    ladder_exports: list[models.ExecutionNarrativeExport] = []
    if cache_scope_ids:
        ladder_exports = (
            db.query(models.ExecutionNarrativeExport)
            .options(
                joinedload(models.ExecutionNarrativeExport.approval_stages)
            )
            .filter(models.ExecutionNarrativeExport.execution_id.in_(list(cache_scope_ids)))
            .all()
        )
        _include_stage_metrics(report, ladder_exports)

    _store_governance_report_cache_entry(
        cache_key,
        report,
        execution_scope=cache_scope_ids,
    )
    return report

