
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from .. import models
from ..eventlog import (
    record_baseline_event,
    record_governance_override_action_event,
)

# purpose: execute governance override workflows and persist auditable action records
# inputs: recommendation metadata, RBAC-verified ORM entities, acting user
# outputs: GovernanceOverrideAction rows with associated baseline/execution side effects
# status: pilot

ActionResult = Tuple[models.GovernanceOverrideAction, Dict[str, Any]]


def _ensure_dict(payload: Dict[str, Any] | None) -> Dict[str, Any]:
    return {key: value for key, value in (payload or {}).items() if value is not None}


def _parse_rule_key(recommendation_id: str, fallback: str | None = None) -> str:
    if ":" in recommendation_id:
        return recommendation_id.split(":", 1)[0]
    return fallback or recommendation_id


def _load_target_reviewer(
    db: Session,
    target_reviewer_id: UUID | None,
) -> models.User | None:
    if target_reviewer_id is None:
        return None
    return db.get(models.User, target_reviewer_id)


def _get_or_initialize_action(
    db: Session,
    *,
    actor: models.User,
    recommendation_id: str,
) -> models.GovernanceOverrideAction:
    record = (
        db.query(models.GovernanceOverrideAction)
        .filter(
            models.GovernanceOverrideAction.recommendation_id == recommendation_id,
            models.GovernanceOverrideAction.actor_id == actor.id,
        )
        .order_by(models.GovernanceOverrideAction.created_at.desc())
        .first()
    )
    if record is None:
        record = models.GovernanceOverrideAction(
            recommendation_id=recommendation_id,
            actor_id=actor.id,
            action="reassign",
            status="accepted",
            reversible=False,
            notes=None,
            meta={},
        )
        db.add(record)
        db.flush()
    return record


def _apply_reassign(
    db: Session,
    *,
    actor: models.User,
    recommendation_id: str,
    baseline: models.GovernanceBaselineVersion,
    target_reviewer: models.User,
    notes: str | None,
) -> Dict[str, Any]:
    reviewer_ids = []
    if isinstance(baseline.reviewer_ids, list):
        reviewer_ids = [str(value) for value in baseline.reviewer_ids if value]
    target_id = str(target_reviewer.id)
    changed = target_id not in reviewer_ids
    if changed:
        reviewer_ids.append(target_id)
        baseline.reviewer_ids = reviewer_ids
        baseline.updated_at = datetime.now(timezone.utc)
    detail = {
        "recommendation_id": recommendation_id,
        "target_reviewer_id": target_id,
        "changed": changed,
    }
    record_baseline_event(
        db,
        baseline,
        action="override_reassign",
        detail=detail,
        actor=actor,
        notes=notes,
    )
    return detail


def _apply_cooldown(
    db: Session,
    *,
    actor: models.User,
    recommendation_id: str,
    execution: models.ProtocolExecution,
    baseline: models.GovernanceBaselineVersion | None,
    notes: str | None,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    detail = {
        "recommendation_id": recommendation_id,
        "cooldown_minutes": metadata.get("cooldown_minutes"),
        "notes": notes,
    }
    if baseline is not None:
        record_baseline_event(
            db,
            baseline,
            action="override_cooldown",
            detail=detail,
            actor=actor,
            notes=notes,
        )
    return detail


def _apply_escalate(
    *,
    recommendation_id: str,
    target_reviewer: models.User | None,
    notes: str | None,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "recommendation_id": recommendation_id,
        "target_reviewer_id": str(target_reviewer.id) if target_reviewer else None,
        "notes": notes,
        "urgency": metadata.get("urgency"),
    }


def accept_override(
    db: Session,
    *,
    actor: models.User,
    recommendation_id: str,
    action: str,
    execution: models.ProtocolExecution,
    baseline: models.GovernanceBaselineVersion | None,
    target_reviewer_id: UUID | None,
    notes: str | None,
    metadata: Dict[str, Any] | None = None,
) -> ActionResult:
    record = _get_or_initialize_action(db, actor=actor, recommendation_id=recommendation_id)
    record.action = action
    record.status = "accepted"
    record.execution_id = execution.id
    record.baseline_id = getattr(baseline, "id", None)
    record.target_reviewer_id = target_reviewer_id
    record.notes = notes
    record.meta = _ensure_dict(metadata)
    record.updated_at = datetime.now(timezone.utc)
    db.flush()
    detail = {
        "baseline_id": str(record.baseline_id) if record.baseline_id else None,
        "target_reviewer_id": str(record.target_reviewer_id) if record.target_reviewer_id else None,
        "notes": notes,
    }
    rule_key = _parse_rule_key(recommendation_id)
    record_governance_override_action_event(
        db,
        execution,
        recommendation_id=recommendation_id,
        rule_key=rule_key,
        action=action,
        status="accepted",
        actor=actor,
        detail=detail,
    )
    return record, detail


def decline_override(
    db: Session,
    *,
    actor: models.User,
    recommendation_id: str,
    action: str,
    execution: models.ProtocolExecution,
    baseline: models.GovernanceBaselineVersion | None,
    notes: str | None,
    metadata: Dict[str, Any] | None = None,
) -> ActionResult:
    record = _get_or_initialize_action(db, actor=actor, recommendation_id=recommendation_id)
    record.action = action
    record.status = "declined"
    record.execution_id = execution.id
    record.baseline_id = getattr(baseline, "id", None)
    record.notes = notes
    record.meta = _ensure_dict(metadata)
    record.updated_at = datetime.now(timezone.utc)
    db.flush()
    detail = {
        "baseline_id": str(record.baseline_id) if record.baseline_id else None,
        "notes": notes,
    }
    rule_key = _parse_rule_key(recommendation_id)
    record_governance_override_action_event(
        db,
        execution,
        recommendation_id=recommendation_id,
        rule_key=rule_key,
        action=action,
        status="declined",
        actor=actor,
        detail=detail,
    )
    return record, detail


def execute_override(
    db: Session,
    *,
    actor: models.User,
    recommendation_id: str,
    action: str,
    execution: models.ProtocolExecution,
    baseline: models.GovernanceBaselineVersion | None,
    target_reviewer_id: UUID | None,
    notes: str | None,
    metadata: Dict[str, Any] | None = None,
) -> ActionResult:
    record = _get_or_initialize_action(db, actor=actor, recommendation_id=recommendation_id)
    target_reviewer = _load_target_reviewer(db, target_reviewer_id)
    record.action = action
    record.execution_id = execution.id
    record.baseline_id = getattr(baseline, "id", None)
    record.target_reviewer_id = getattr(target_reviewer, "id", None)
    record.notes = notes
    record.meta = _ensure_dict(metadata)
    record.reversible = bool(metadata.get("reversible")) if isinstance(metadata, dict) else False

    rule_key = _parse_rule_key(recommendation_id)
    metadata_dict = record.meta
    detail: Dict[str, Any]

    if action == "reassign":
        if baseline is None or target_reviewer is None:
            raise ValueError("Reassign actions require baseline and target reviewer context")
        detail = _apply_reassign(
            db,
            actor=actor,
            recommendation_id=recommendation_id,
            baseline=baseline,
            target_reviewer=target_reviewer,
            notes=notes,
        )
    elif action == "cooldown":
        detail = _apply_cooldown(
            db,
            actor=actor,
            recommendation_id=recommendation_id,
            execution=execution,
            baseline=baseline,
            notes=notes,
            metadata=metadata_dict,
        )
    elif action == "escalate":
        detail = _apply_escalate(
            recommendation_id=recommendation_id,
            target_reviewer=target_reviewer,
            notes=notes,
            metadata=metadata_dict,
        )
    else:
        raise ValueError(f"Unsupported override action: {action}")

    record.status = "executed"
    record.updated_at = datetime.now(timezone.utc)
    db.flush()

    detail.update(
        {
            "baseline_id": str(record.baseline_id) if record.baseline_id else None,
            "target_reviewer_id": str(record.target_reviewer_id)
            if record.target_reviewer_id
            else None,
        }
    )
    record_governance_override_action_event(
        db,
        execution,
        recommendation_id=recommendation_id,
        rule_key=rule_key,
        action=action,
        status="executed",
        actor=actor,
        detail=detail,
    )
    return record, detail


__all__ = [
    "accept_override",
    "decline_override",
    "execute_override",
]
