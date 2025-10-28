"""Governance decision timeline aggregation utilities."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Sequence
from uuid import UUID, NAMESPACE_URL, uuid5

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..analytics.governance import compute_governance_analytics

TIMELINE_EVENT_TYPES: tuple[str, ...] = (
    "governance.recommendation.override",
    "governance.override.action",
)


@dataclass(slots=True)
class _Cursor:
    """Internal cursor structure for timeline pagination."""

    # purpose: encapsulate decoded cursor data for deterministic pagination
    # inputs: encoded cursor payload from client request
    # outputs: comparable fields for filtering query results
    # status: pilot

    occurred_at: datetime
    entry_id: UUID

    @classmethod
    def decode(cls, value: str | None) -> "_Cursor | None":
        if not value:
            return None
        try:
            payload = base64.urlsafe_b64decode(value.encode("utf-8"))
            raw = json.loads(payload.decode("utf-8"))
            occurred_at = datetime.fromisoformat(raw["occurred_at"])
            entry_id = UUID(raw["entry_id"])
        except Exception:  # pragma: no cover - defensive guard
            return None
        return cls(occurred_at=occurred_at, entry_id=entry_id)

    def encode(self) -> str:
        data = {
            "occurred_at": self.occurred_at.isoformat(),
            "entry_id": str(self.entry_id),
        }
        payload = json.dumps(data).encode("utf-8")
        return base64.urlsafe_b64encode(payload).decode("utf-8")


def _apply_execution_rbac_filters(
    query,
    user: models.User,
    membership_ids: set[UUID],
):
    """Apply RBAC filters to execution-sourced queries."""

    # purpose: scope execution queries to RBAC-permitted templates and actors
    # inputs: SQLAlchemy query, requesting user, cached membership ids
    # outputs: filtered query enforcing governance console RBAC rules
    # status: pilot

    if user.is_admin:
        return query
    access_filters = [models.ProtocolExecution.run_by == user.id]
    access_filters.append(models.ProtocolTemplate.team_id.is_(None))
    if membership_ids:
        access_filters.append(models.ProtocolTemplate.team_id.in_(list(membership_ids)))
    return query.filter(or_(*access_filters))


def _stable_entry_uuid(entry_id: str) -> UUID:
    """Return a deterministic UUID for timeline pagination cursors."""

    # purpose: normalise composite string identifiers for cursor encoding
    # inputs: timeline entry id string (uuid or analytics prefixed token)
    # outputs: UUID safe for cursor comparisons
    # status: pilot

    if entry_id.startswith("analytics:"):
        return uuid5(NAMESPACE_URL, entry_id)
    return UUID(entry_id)


def _normalise_timestamp(value: datetime | None) -> datetime:
    """Return a timezone-aware datetime for sorting operations."""

    # purpose: align naive database timestamps with UTC ordering for timeline feeds
    # inputs: optional datetime sourced from ORM rows
    # outputs: timezone-aware datetime anchored in UTC
    # status: pilot

    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _build_override_lineage_context(
    override: models.GovernanceOverrideAction | None,
) -> schemas.GovernanceOverrideLineageContext | None:
    """Return structured lineage context for override actions."""

    # purpose: translate ORM override lineage records into schema payloads
    # inputs: GovernanceOverrideAction with optional lineage relationship
    # outputs: GovernanceOverrideLineageContext for timeline entries
    # status: pilot

    if override is None or override.lineage is None:
        return None

    lineage = override.lineage
    scenario_payload: Dict[str, Any] | None = None
    if lineage.scenario is not None:
        folder_name = None
        if getattr(lineage.scenario, "folder", None) is not None:
            folder_name = lineage.scenario.folder.name
        scenario_payload = {
            "id": lineage.scenario.id,
            "name": lineage.scenario.name,
            "folder_id": lineage.scenario.folder_id,
            "folder_name": folder_name,
            "owner_id": lineage.scenario.owner_id,
        }
    elif lineage.scenario_snapshot:
        scenario_payload = dict(lineage.scenario_snapshot)
        if lineage.scenario_id and "id" not in scenario_payload:
            scenario_payload["id"] = lineage.scenario_id
    elif lineage.scenario_id:
        scenario_payload = {"id": lineage.scenario_id}

    notebook_payload: Dict[str, Any] | None = None
    if lineage.notebook_entry is not None:
        notebook_payload = {
            "id": lineage.notebook_entry.id,
            "title": lineage.notebook_entry.title,
            "execution_id": lineage.notebook_entry.execution_id,
        }
    elif lineage.notebook_snapshot:
        notebook_payload = dict(lineage.notebook_snapshot)
        if lineage.notebook_entry_id and "id" not in notebook_payload:
            notebook_payload["id"] = lineage.notebook_entry_id
    elif lineage.notebook_entry_id:
        notebook_payload = {"id": lineage.notebook_entry_id}

    captured_by_summary: schemas.GovernanceActorSummary | None = None
    if lineage.captured_by is not None:
        captured_by_summary = schemas.GovernanceActorSummary(
            id=lineage.captured_by.id,
            name=lineage.captured_by.full_name,
            email=lineage.captured_by.email,
        )

    return schemas.GovernanceOverrideLineageContext(
        scenario=schemas.GovernanceScenarioLineage.model_validate(scenario_payload)
        if scenario_payload
        else None,
        notebook_entry=schemas.GovernanceNotebookLineage.model_validate(notebook_payload)
        if notebook_payload
        else None,
        captured_at=lineage.captured_at,
        captured_by=captured_by_summary,
        metadata=lineage.meta or {},
    )


def _load_governance_events(
    db: Session,
    user: models.User,
    membership_ids: set[UUID],
    execution_ids: set[UUID] | None,
    cursor: _Cursor | None,
    limit: int,
) -> list[schemas.GovernanceDecisionTimelineEntry]:
    """Return execution event-backed governance timeline entries."""

    # purpose: hydrate governance recommendation/override execution events
    # inputs: db session, rbac context, optional execution scope, pagination cursor, limit
    # outputs: list of GovernanceDecisionTimelineEntry from execution_events
    # status: pilot

    query = (
        db.query(models.ExecutionEvent)
        .join(models.ProtocolExecution)
        .join(models.ProtocolTemplate, isouter=True)
        .options(joinedload(models.ExecutionEvent.actor))
        .filter(models.ExecutionEvent.event_type.in_(TIMELINE_EVENT_TYPES))
    )
    if execution_ids:
        query = query.filter(models.ExecutionEvent.execution_id.in_(list(execution_ids)))
    query = _apply_execution_rbac_filters(query, user, membership_ids)
    query = query.order_by(models.ExecutionEvent.created_at.desc(), models.ExecutionEvent.id.desc())
    events: list[models.ExecutionEvent] = query.limit(limit * 2).all()

    execution_hashes: set[str] = set()
    for event in events:
        payload = event.payload or {}
        detail_payload = payload.get("detail") if isinstance(payload.get("detail"), dict) else {}
        execution_hash = detail_payload.get("execution_hash") if isinstance(detail_payload, dict) else None
        if execution_hash:
            execution_hashes.add(str(execution_hash))

    override_index: dict[str, models.GovernanceOverrideAction] = {}
    if execution_hashes:
        overrides = (
            db.query(models.GovernanceOverrideAction)
            .options(
                joinedload(models.GovernanceOverrideAction.lineage)
                .joinedload(models.GovernanceOverrideLineage.scenario)
                .joinedload(models.ExperimentScenario.folder),
                joinedload(models.GovernanceOverrideAction.lineage)
                .joinedload(models.GovernanceOverrideLineage.notebook_entry),
                joinedload(models.GovernanceOverrideAction.lineage)
                .joinedload(models.GovernanceOverrideLineage.captured_by),
            )
            .filter(models.GovernanceOverrideAction.execution_hash.in_(list(execution_hashes)))
            .all()
        )
        override_index = {
            str(override.execution_hash): override
            for override in overrides
            if override.execution_hash
        }

    entries: list[schemas.GovernanceDecisionTimelineEntry] = []
    for event in events:
        occurred_at = _normalise_timestamp(event.created_at)
        if cursor and (
            occurred_at > cursor.occurred_at
            or (occurred_at == cursor.occurred_at and event.id >= cursor.entry_id)
        ):
            continue
        payload = event.payload or {}
        entry_type = (
            "override_recommendation"
            if event.event_type == "governance.recommendation.override"
            else "override_action"
        )
        actor = event.actor
        actor_payload = (
            schemas.GovernanceActorSummary(
                id=actor.id,
                name=actor.full_name,
                email=actor.email,
            )
            if actor is not None
            else None
        )
        detail_payload: Dict[str, Any] = payload.get("detail", {}) if isinstance(payload.get("detail"), dict) else {}
        lineage_context: schemas.GovernanceOverrideLineageContext | None = None
        execution_hash = detail_payload.get("execution_hash") if isinstance(detail_payload, dict) else None
        if execution_hash and entry_type == "override_action":
            override = override_index.get(str(execution_hash))
            lineage_context = _build_override_lineage_context(override)
            if lineage_context is not None:
                detail_payload.setdefault("lineage", lineage_context.model_dump(mode="json"))
        entries.append(
            schemas.GovernanceDecisionTimelineEntry(
                entry_id=str(event.id),
                entry_type=entry_type,
                occurred_at=occurred_at,
                execution_id=event.execution_id,
                baseline_id=payload.get("baseline_id"),
                rule_key=payload.get("rule_key"),
                action=payload.get("action"),
                status=payload.get("status"),
                actor=actor_payload,
                summary=payload.get("summary"),
                detail=payload,
                lineage=lineage_context,
            )
        )
        if len(entries) >= limit:
            break
    return entries


def _load_baseline_events(
    db: Session,
    user: models.User,
    membership_ids: set[UUID],
    execution_ids: set[UUID] | None,
    cursor: _Cursor | None,
    limit: int,
) -> list[schemas.GovernanceDecisionTimelineEntry]:
    """Return governance baseline lifecycle events within RBAC scope."""

    # purpose: translate governance_baseline_events rows into timeline entries
    # inputs: db session, rbac context, optional execution scope, pagination cursor, limit
    # outputs: list of GovernanceDecisionTimelineEntry from baseline events
    # status: pilot

    query = (
        db.query(models.GovernanceBaselineEvent)
        .join(models.GovernanceBaselineVersion)
        .join(models.ProtocolExecution)
        .join(models.ProtocolTemplate, isouter=True)
        .options(
            joinedload(models.GovernanceBaselineEvent.actor),
            joinedload(models.GovernanceBaselineEvent.baseline),
        )
    )
    if execution_ids:
        query = query.filter(models.GovernanceBaselineVersion.execution_id.in_(list(execution_ids)))
    if not user.is_admin:
        access_filters = [models.ProtocolExecution.run_by == user.id]
        access_filters.append(models.ProtocolTemplate.team_id.is_(None))
        if membership_ids:
            access_filters.append(models.ProtocolTemplate.team_id.in_(list(membership_ids)))
        query = query.filter(or_(*access_filters))
    query = query.order_by(models.GovernanceBaselineEvent.created_at.desc(), models.GovernanceBaselineEvent.id.desc())
    events: list[models.GovernanceBaselineEvent] = query.limit(limit * 2).all()

    entries: list[schemas.GovernanceDecisionTimelineEntry] = []
    for event in events:
        occurred_at = _normalise_timestamp(event.created_at)
        if cursor and (
            occurred_at > cursor.occurred_at
            or (occurred_at == cursor.occurred_at and event.id >= cursor.entry_id)
        ):
            continue
        actor = event.actor
        actor_payload = (
            schemas.GovernanceActorSummary(
                id=actor.id,
                name=actor.full_name,
                email=actor.email,
            )
            if actor is not None
            else None
        )
        entries.append(
            schemas.GovernanceDecisionTimelineEntry(
                entry_id=str(event.id),
                entry_type="baseline_event",
                occurred_at=occurred_at,
                execution_id=event.baseline.execution_id if event.baseline else None,
                baseline_id=event.baseline_id,
                rule_key=None,
                action=event.action,
                status=None,
                actor=actor_payload,
                summary=event.notes,
                detail=event.detail or {},
            )
        )
        if len(entries) >= limit:
            break
    return entries


def _load_coaching_notes(
    db: Session,
    user: models.User,
    membership_ids: set[UUID],
    execution_ids: set[UUID] | None,
    cursor: _Cursor | None,
    limit: int,
) -> list[schemas.GovernanceDecisionTimelineEntry]:
    """Return governance coaching notes respecting RBAC scope."""

    # purpose: surface latest coaching notes and thread counts in decision timeline
    # inputs: db session, rbac context, optional execution scope, pagination cursor, limit
    # outputs: list of GovernanceDecisionTimelineEntry derived from coaching notes
    # status: experimental

    query = (
        db.query(models.GovernanceCoachingNote)
        .join(models.GovernanceOverrideAction)
        .outerjoin(
            models.ProtocolExecution,
            models.GovernanceOverrideAction.execution_id == models.ProtocolExecution.id,
        )
        .outerjoin(
            models.ProtocolTemplate,
            models.ProtocolExecution.template_id == models.ProtocolTemplate.id,
        )
        .outerjoin(
            models.GovernanceBaselineVersion,
            models.GovernanceCoachingNote.baseline_id == models.GovernanceBaselineVersion.id,
        )
        .options(
            joinedload(models.GovernanceCoachingNote.author),
            joinedload(models.GovernanceCoachingNote.override),
        )
    )
    if execution_ids:
        exec_ids = list(execution_ids)
        query = query.filter(
            or_(
                models.GovernanceCoachingNote.execution_id.in_(exec_ids),
                models.GovernanceOverrideAction.execution_id.in_(exec_ids),
                models.GovernanceBaselineVersion.execution_id.in_(exec_ids),
            )
        )
    if not user.is_admin:
        membership_list = list(membership_ids)
        access_filters = [
            models.GovernanceOverrideAction.actor_id == user.id,
            models.GovernanceOverrideAction.target_reviewer_id == user.id,
            models.ProtocolExecution.run_by == user.id,
            models.ProtocolTemplate.team_id.is_(None),
        ]
        if membership_list:
            access_filters.append(models.ProtocolTemplate.team_id.in_(membership_list))
            access_filters.append(models.GovernanceBaselineVersion.team_id.in_(membership_list))
        query = query.filter(or_(*access_filters))
    query = query.order_by(
        models.GovernanceCoachingNote.created_at.desc(),
        models.GovernanceCoachingNote.id.desc(),
    )
    notes: list[models.GovernanceCoachingNote] = query.limit(limit * 2).all()

    override_ids = {note.override_id for note in notes}
    thread_roots = {note.thread_root_id or note.id for note in notes if note}
    reply_index: dict[UUID, int] = {}
    if override_ids and thread_roots:
        rows = (
            db.query(
                models.GovernanceCoachingNote.thread_root_id,
                func.count(models.GovernanceCoachingNote.id),
            )
            .filter(
                models.GovernanceCoachingNote.override_id.in_(list(override_ids)),
                models.GovernanceCoachingNote.thread_root_id.in_(list(thread_roots)),
            )
            .group_by(models.GovernanceCoachingNote.thread_root_id)
            .all()
        )
        for root_id, count in rows:
            if root_id is None:
                continue
            reply_index[root_id] = int(count) - 1

    entries: list[schemas.GovernanceDecisionTimelineEntry] = []
    for note in notes:
        occurred_at = _normalise_timestamp(note.created_at)
        if cursor and (
            occurred_at > cursor.occurred_at
            or (occurred_at == cursor.occurred_at and note.id >= cursor.entry_id)
        ):
            continue
        author = note.author
        actor_payload = (
            schemas.GovernanceActorSummary(
                id=author.id,
                name=author.full_name,
                email=author.email,
            )
            if author is not None
            else None
        )
        reply_count = reply_index.get(note.thread_root_id or note.id, 0)
        raw_meta = dict(note.meta or {})
        history = raw_meta.pop("moderation_history", [])
        normalized_history = history if isinstance(history, list) else []
        detail_payload: Dict[str, Any] = {
            "note_id": str(note.id),
            "override_id": str(note.override_id),
            "body": note.body,
            "moderation_state": note.moderation_state,
            "thread_root_id": str(note.thread_root_id) if note.thread_root_id else None,
            "parent_id": str(note.parent_id) if note.parent_id else None,
            "reply_count": reply_count,
            "metadata": raw_meta,
            "moderation_history": normalized_history,
        }
        entries.append(
            schemas.GovernanceDecisionTimelineEntry(
                entry_id=str(note.id),
                entry_type="coaching_note",
                occurred_at=occurred_at,
                execution_id=note.execution_id
                or (note.override.execution_id if note.override else None),
                baseline_id=note.baseline_id
                or (note.override.baseline_id if note.override else None),
                rule_key=None,
                action=None,
                status=note.moderation_state,
                actor=actor_payload,
                summary="Coaching note added" if note.parent_id is None else "Coaching reply posted",
                detail=detail_payload,
            )
        )
        if len(entries) >= limit:
            break
    return entries


def _load_analytics_snapshots(
    db: Session,
    user: models.User,
    membership_ids: set[UUID],
    execution_ids: set[UUID] | None,
    limit: int,
) -> list[schemas.GovernanceDecisionTimelineEntry]:
    """Return analytics snapshot entries derived from cadence reports."""

    # purpose: surface cadence analytics alongside discrete governance events
    # inputs: db session, rbac context, optional execution scope, limit for entry count
    # outputs: list of GovernanceDecisionTimelineEntry summarising analytics reports
    # status: pilot

    analytics = compute_governance_analytics(
        db,
        user,
        team_ids=membership_ids,
        execution_ids=list(execution_ids) if execution_ids else None,
        limit=limit,
        include_previews=False,
    )
    entries: list[schemas.GovernanceDecisionTimelineEntry] = []
    generated_at_candidates = [
        summary.generated_at
        for summary in analytics.results
        if getattr(summary, "generated_at", None) is not None
    ]
    report_timestamp = (
        max(generated_at_candidates)
        if generated_at_candidates
        else datetime.now(timezone.utc)
    )
    lineage_summary_payload = (
        analytics.lineage_summary.model_dump(mode="json")
        if getattr(analytics, "lineage_summary", None) is not None
        else None
    )
    for reviewer in analytics.reviewer_cadence:
        occurred_at = report_timestamp
        detail = reviewer.model_dump(mode="json")
        if lineage_summary_payload:
            detail["lineage_summary"] = lineage_summary_payload
        entries.append(
            schemas.GovernanceDecisionTimelineEntry(
                entry_id=f"analytics:{reviewer.reviewer_id or 'global'}:{occurred_at.isoformat()}",
                entry_type="analytics_snapshot",
                occurred_at=occurred_at,
                execution_id=None,
                baseline_id=None,
                rule_key=None,
                action=None,
                status=None,
                actor=None,
                summary="Reviewer cadence snapshot",
                detail=detail,
            )
        )
        if len(entries) >= limit:
            break
    return entries


def load_governance_decision_timeline(
    db: Session,
    user: models.User,
    *,
    membership_ids: set[UUID],
    execution_ids: Sequence[UUID] | None = None,
    cursor: str | None = None,
    limit: int = 50,
) -> schemas.GovernanceDecisionTimelinePage:
    """Return composite governance decision timeline entries."""

    # purpose: assemble override, baseline, and analytics artefacts into a unified feed
    # inputs: db session, requesting user, membership scope, optional execution filter, pagination params
    # outputs: GovernanceDecisionTimelinePage for experiment console consumption
    # status: pilot

    safe_limit = max(1, min(limit, 200))
    execution_scope = set(execution_ids or [])
    decoded_cursor = _Cursor.decode(cursor)

    event_entries = _load_governance_events(
        db,
        user,
        membership_ids,
        execution_scope,
        decoded_cursor,
        safe_limit,
    )
    baseline_entries = _load_baseline_events(
        db,
        user,
        membership_ids,
        execution_scope,
        decoded_cursor,
        safe_limit,
    )
    coaching_entries = _load_coaching_notes(
        db,
        user,
        membership_ids,
        execution_scope,
        decoded_cursor,
        safe_limit,
    )
    analytics_entries = _load_analytics_snapshots(
        db,
        user,
        membership_ids,
        execution_scope,
        safe_limit,
    )

    combined = event_entries + baseline_entries + coaching_entries + analytics_entries
    combined.sort(key=lambda item: (item.occurred_at, item.entry_id), reverse=True)
    combined = combined[:safe_limit]

    next_cursor_value: str | None = None
    if len(combined) == safe_limit:
        last_entry = combined[-1]
        cursor_obj = _Cursor(
            occurred_at=last_entry.occurred_at,
            entry_id=_stable_entry_uuid(last_entry.entry_id),
        )
        next_cursor_value = cursor_obj.encode()

    return schemas.GovernanceDecisionTimelinePage(entries=combined, next_cursor=next_cursor_value)
