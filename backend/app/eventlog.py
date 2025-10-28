"""Utilities for recording execution timeline events."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from . import models

# purpose: shareable helpers for persisting execution timeline events across services
# inputs: SQLAlchemy session, protocol execution instance, event metadata
# outputs: normalized ExecutionEvent rows with sequential ordering
# status: pilot


def record_execution_event(
    db: Session,
    execution: models.ProtocolExecution,
    event_type: str,
    payload: dict[str, Any],
    actor: models.User | None = None,
) -> models.ExecutionEvent:
    """Persist a structured execution event for timeline replay."""

    payload_dict = payload if isinstance(payload, dict) else {}
    latest = (
        db.query(models.ExecutionEvent)
        .filter(models.ExecutionEvent.execution_id == execution.id)
        .order_by(models.ExecutionEvent.sequence.desc())
        .first()
    )
    next_sequence = 1 if latest is None else latest.sequence + 1
    event = models.ExecutionEvent(
        execution_id=execution.id,
        event_type=event_type,
        payload=payload_dict,
        actor_id=getattr(actor, "id", None),
        sequence=next_sequence,
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    return event


def record_baseline_event(
    db: Session,
    baseline: models.GovernanceBaselineVersion,
    action: str,
    detail: dict[str, Any],
    actor: models.User,
    notes: str | None = None,
) -> models.GovernanceBaselineEvent:
    """Persist auditable baseline lifecycle events."""

    # purpose: capture baseline governance lifecycle transitions for auditing
    # inputs: session handle, baseline entity, action name, detail payload, actor
    # outputs: GovernanceBaselineEvent row persisted for traceability
    # status: draft

    payload_dict = detail if isinstance(detail, dict) else {}
    event = models.GovernanceBaselineEvent(
        baseline_id=baseline.id,
        action=action,
        detail=payload_dict,
        notes=notes,
        performed_by_id=actor.id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    return event


def record_governance_recommendation_event(
    db: Session,
    execution: models.ProtocolExecution,
    rule_key: str,
    recommendation: dict[str, Any],
    actor: models.User | None = None,
    opted_out: bool = False,
) -> models.ExecutionEvent:
    """Persist governance override recommendation events with provenance."""

    # purpose: log governance override recommendations for audit and replay
    # inputs: execution context, rule identifier, recommendation payload, actor, opt-out flag
    # outputs: ExecutionEvent entries capturing override advice lineage
    # status: pilot

    payload = {
        "rule_key": rule_key,
        "recommendation": recommendation,
        "reviewer_id": recommendation.get("reviewer_id"),
        "opted_out": opted_out,
    }
    return record_execution_event(
        db,
        execution,
        event_type="governance.recommendation.override",
        payload=payload,
        actor=actor,
    )


def record_governance_override_action_event(
    db: Session,
    execution: models.ProtocolExecution,
    *,
    recommendation_id: str,
    rule_key: str,
    action: str,
    status: str,
    actor: models.User,
    detail: dict[str, Any] | None = None,
) -> models.ExecutionEvent:
    """Persist override action outcomes for governance replay."""

    # purpose: log override action execution results with minimal lineage payloads
    # inputs: execution context, recommendation identifiers, action metadata, actor
    # outputs: ExecutionEvent row for governance timeline reconstruction
    # status: pilot

    payload = {
        "recommendation_id": recommendation_id,
        "rule_key": rule_key,
        "action": action,
        "status": status,
        "actor_id": str(actor.id),
    }
    detail_payload = detail or {}
    payload.update({key: value for key, value in detail_payload.items() if key in {
        "baseline_id",
        "target_reviewer_id",
        "notes",
        "changed",
        "cooldown_minutes",
        "cooldown_expires_at",
        "urgency",
        "reviewer_ids_before",
        "reviewer_ids_after",
        "execution_hash",
        "reversal",
        "reversal_notes",
        "reversal_event",
    }})
    payload["detail"] = detail_payload
    return record_execution_event(
        db,
        execution,
        event_type="governance.override.action",
        payload=payload,
        actor=actor,
    )

