"""Governance decision timeline aggregation utilities."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence
from uuid import UUID, NAMESPACE_URL, uuid5

from sqlalchemy import or_
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
    for reviewer in analytics.reviewer_cadence:
        occurred_at = report_timestamp
        detail = reviewer.model_dump(mode="json")
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
    analytics_entries = _load_analytics_snapshots(
        db,
        user,
        membership_ids,
        execution_scope,
        safe_limit,
    )

    combined = event_entries + baseline_entries + analytics_entries
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
