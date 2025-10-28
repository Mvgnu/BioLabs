
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from .. import models, schemas
from ..eventlog import (
    record_baseline_event,
    record_governance_override_action_event,
)

# purpose: execute governance override workflows and persist auditable action records
# inputs: recommendation metadata, RBAC-verified ORM entities, acting user
# outputs: GovernanceOverrideAction rows with associated baseline/execution side effects
# status: pilot

ActionResult = Tuple[models.GovernanceOverrideAction, Dict[str, Any]]


def _stable_json_dumps(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, default=str)


def _compute_execution_hash(
    *,
    recommendation_id: str,
    actor_id: UUID,
    action: str,
    status: str,
    execution_id: UUID | None,
    baseline_id: UUID | None,
    target_reviewer_id: UUID | None,
    metadata: Dict[str, Any] | None,
) -> str:
    basis = {
        "recommendation_id": recommendation_id,
        "actor_id": str(actor_id),
        "action": action,
        "status": status,
        "execution_id": str(execution_id) if execution_id else None,
        "baseline_id": str(baseline_id) if baseline_id else None,
        "target_reviewer_id": str(target_reviewer_id) if target_reviewer_id else None,
        "metadata": metadata or {},
    }
    digest = hashlib.sha256(_stable_json_dumps(basis).encode("utf-8"))
    return digest.hexdigest()


def _get_action_by_hash(
    db: Session,
    *,
    execution_hash: str,
) -> models.GovernanceOverrideAction | None:
    return (
        db.query(models.GovernanceOverrideAction)
        .filter(models.GovernanceOverrideAction.execution_hash == execution_hash)
        .first()
    )


def _ensure_dict(payload: Dict[str, Any] | None) -> Dict[str, Any]:
    return {key: value for key, value in (payload or {}).items() if value is not None}


def _compact_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in payload.items() if value is not None}


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
            detail_snapshot={},
        )
        db.add(record)
        db.flush()
    return record


def _persist_action(
    db: Session,
    record: models.GovernanceOverrideAction,
    *,
    status: str,
    detail: Dict[str, Any],
    execution_hash: str,
) -> None:
    record.status = status
    record.execution_hash = execution_hash
    record.detail_snapshot = detail
    record.updated_at = datetime.now(timezone.utc)
    db.flush()


def _persist_override_lineage(
    db: Session,
    record: models.GovernanceOverrideAction,
    *,
    actor: models.User,
    payload: schemas.GovernanceOverrideLineagePayload | None,
) -> models.GovernanceOverrideLineage | None:
    if payload is None:
        return record.lineage

    lineage = record.lineage or models.GovernanceOverrideLineage(override=record)
    if lineage.id is None:
        db.add(lineage)

    lineage.scenario_id = payload.scenario_id
    lineage.notebook_entry_id = payload.notebook_entry_id

    scenario_snapshot: Dict[str, Any] = {}
    if payload.scenario_id is not None:
        scenario = db.get(models.ExperimentScenario, payload.scenario_id)
        if scenario is not None:
            folder_name = None
            folder_id = getattr(scenario, "folder_id", None)
            if getattr(scenario, "folder", None) is not None:
                folder_name = scenario.folder.name
            scenario_snapshot = _compact_snapshot(
                {
                    "id": str(scenario.id),
                    "name": scenario.name,
                    "folder_id": str(folder_id) if folder_id else None,
                    "folder_name": folder_name,
                    "owner_id": str(scenario.owner_id) if scenario.owner_id else None,
                }
            )
    lineage.scenario_snapshot = scenario_snapshot

    notebook_snapshot: Dict[str, Any] = {}
    if payload.notebook_entry_id is not None:
        notebook = db.get(models.NotebookEntry, payload.notebook_entry_id)
        if notebook is not None:
            notebook_snapshot = _compact_snapshot(
                {
                    "id": str(notebook.id),
                    "title": notebook.title,
                    "execution_id": str(notebook.execution_id)
                    if notebook.execution_id
                    else None,
                }
            )
    lineage.notebook_snapshot = notebook_snapshot

    metadata = _ensure_dict(payload.metadata)
    if payload.notebook_entry_version_id is not None:
        metadata.setdefault(
            "notebook_entry_version_id",
            str(payload.notebook_entry_version_id),
        )
    lineage.meta = metadata
    lineage.captured_by_id = actor.id
    lineage.captured_at = datetime.now(timezone.utc)
    db.flush()
    return lineage


def _serialize_lineage(
    lineage: models.GovernanceOverrideLineage | None,
) -> Dict[str, Any]:
    if lineage is None:
        return {}

    scenario_snapshot = dict(lineage.scenario_snapshot or {})
    if lineage.scenario_id and "id" not in scenario_snapshot:
        scenario_snapshot["id"] = str(lineage.scenario_id)
    notebook_snapshot = dict(lineage.notebook_snapshot or {})
    if lineage.notebook_entry_id and "id" not in notebook_snapshot:
        notebook_snapshot["id"] = str(lineage.notebook_entry_id)

    payload: Dict[str, Any] = {
        "captured_at": lineage.captured_at.isoformat()
        if lineage.captured_at
        else None,
        "captured_by_id": str(lineage.captured_by_id) if lineage.captured_by_id else None,
        "metadata": dict(lineage.meta or {}),
    }
    if scenario_snapshot:
        payload["scenario"] = scenario_snapshot
    if notebook_snapshot:
        payload["notebook_entry"] = notebook_snapshot
    return _compact_snapshot(payload)


def _apply_reassign(
    db: Session,
    *,
    actor: models.User,
    recommendation_id: str,
    baseline: models.GovernanceBaselineVersion,
    target_reviewer: models.User,
    notes: str | None,
) -> Dict[str, Any]:
    reviewer_ids: list[str] = []
    if isinstance(baseline.reviewer_ids, list):
        reviewer_ids = [str(value) for value in baseline.reviewer_ids if value]
    target_id = str(target_reviewer.id)
    before = list(reviewer_ids)
    changed = target_id not in reviewer_ids
    if changed:
        reviewer_ids.append(target_id)
        baseline.reviewer_ids = reviewer_ids
        baseline.updated_at = datetime.now(timezone.utc)
    detail = {
        "recommendation_id": recommendation_id,
        "target_reviewer_id": target_id,
        "changed": changed,
        "reviewer_ids_before": before,
        "reviewer_ids_after": list(reviewer_ids),
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


def _reverse_reassign(
    db: Session,
    *,
    actor: models.User,
    recommendation_id: str,
    baseline: models.GovernanceBaselineVersion,
    target_reviewer_id: UUID | None,
    notes: str | None,
) -> Dict[str, Any]:
    reviewer_ids: list[str] = []
    if isinstance(baseline.reviewer_ids, list):
        reviewer_ids = [str(value) for value in baseline.reviewer_ids if value]
    target = str(target_reviewer_id) if target_reviewer_id else None
    before = list(reviewer_ids)
    changed = False
    if target and target in reviewer_ids:
        reviewer_ids = [value for value in reviewer_ids if value != target]
        baseline.reviewer_ids = reviewer_ids
        baseline.updated_at = datetime.now(timezone.utc)
        changed = True
    detail = {
        "recommendation_id": recommendation_id,
        "target_reviewer_id": target,
        "changed": changed,
        "reviewer_ids_before": before,
        "reviewer_ids_after": list(reviewer_ids),
    }
    record_baseline_event(
        db,
        baseline,
        action="override_reassign_reversed",
        detail=detail,
        actor=actor,
        notes=notes,
    )
    return detail


def _reverse_cooldown(
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
        "execution_id": str(execution.id),
    }
    if baseline is not None:
        record_baseline_event(
            db,
            baseline,
            action="override_cooldown_reversed",
            detail=detail,
            actor=actor,
            notes=notes,
        )
    return detail


def _reverse_escalate(
    *,
    recommendation_id: str,
    target_reviewer_id: UUID | None,
    notes: str | None,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "recommendation_id": recommendation_id,
        "target_reviewer_id": str(target_reviewer_id) if target_reviewer_id else None,
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
    lineage: schemas.GovernanceOverrideLineagePayload | None = None,
) -> ActionResult:
    sanitized_metadata = _ensure_dict(metadata)
    execution_hash = _compute_execution_hash(
        recommendation_id=recommendation_id,
        actor_id=actor.id,
        action=action,
        status="accepted",
        execution_id=execution.id,
        baseline_id=getattr(baseline, "id", None),
        target_reviewer_id=target_reviewer_id,
        metadata=sanitized_metadata,
    )
    existing = _get_action_by_hash(db, execution_hash=execution_hash)
    if existing is not None:
        return existing, dict(existing.detail_snapshot or {})

    record = _get_or_initialize_action(db, actor=actor, recommendation_id=recommendation_id)
    record.action = action
    record.execution_id = execution.id
    record.baseline_id = getattr(baseline, "id", None)
    record.target_reviewer_id = target_reviewer_id
    record.notes = notes
    record.meta = sanitized_metadata
    detail = {
        "baseline_id": str(record.baseline_id) if record.baseline_id else None,
        "target_reviewer_id": str(record.target_reviewer_id) if record.target_reviewer_id else None,
        "notes": notes,
        "execution_hash": execution_hash,
    }
    lineage_record = _persist_override_lineage(
        db,
        record,
        actor=actor,
        payload=lineage,
    )
    if lineage_record is not None:
        detail["lineage"] = _serialize_lineage(lineage_record)
    _persist_action(
        db,
        record,
        status="accepted",
        detail=detail,
        execution_hash=execution_hash,
    )
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
    lineage: schemas.GovernanceOverrideLineagePayload | None = None,
) -> ActionResult:
    sanitized_metadata = _ensure_dict(metadata)
    execution_hash = _compute_execution_hash(
        recommendation_id=recommendation_id,
        actor_id=actor.id,
        action=action,
        status="declined",
        execution_id=execution.id,
        baseline_id=getattr(baseline, "id", None),
        target_reviewer_id=None,
        metadata=sanitized_metadata,
    )
    existing = _get_action_by_hash(db, execution_hash=execution_hash)
    if existing is not None:
        return existing, dict(existing.detail_snapshot or {})

    record = _get_or_initialize_action(db, actor=actor, recommendation_id=recommendation_id)
    record.action = action
    record.execution_id = execution.id
    record.baseline_id = getattr(baseline, "id", None)
    record.notes = notes
    record.meta = sanitized_metadata
    detail = {
        "baseline_id": str(record.baseline_id) if record.baseline_id else None,
        "notes": notes,
        "execution_hash": execution_hash,
    }
    lineage_record = _persist_override_lineage(
        db,
        record,
        actor=actor,
        payload=lineage,
    )
    if lineage_record is not None:
        detail["lineage"] = _serialize_lineage(lineage_record)
    _persist_action(
        db,
        record,
        status="declined",
        detail=detail,
        execution_hash=execution_hash,
    )
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
    lineage: schemas.GovernanceOverrideLineagePayload | None = None,
) -> ActionResult:
    sanitized_metadata = _ensure_dict(metadata)
    execution_hash = _compute_execution_hash(
        recommendation_id=recommendation_id,
        actor_id=actor.id,
        action=action,
        status="executed",
        execution_id=execution.id,
        baseline_id=getattr(baseline, "id", None),
        target_reviewer_id=target_reviewer_id,
        metadata=sanitized_metadata,
    )
    existing = _get_action_by_hash(db, execution_hash=execution_hash)
    if existing is not None:
        return existing, dict(existing.detail_snapshot or {})

    record = _get_or_initialize_action(db, actor=actor, recommendation_id=recommendation_id)
    target_reviewer = _load_target_reviewer(db, target_reviewer_id)
    record.action = action
    record.execution_id = execution.id
    record.baseline_id = getattr(baseline, "id", None)
    record.target_reviewer_id = getattr(target_reviewer, "id", None)
    record.notes = notes
    record.meta = sanitized_metadata
    record.reversible = bool(sanitized_metadata.get("reversible"))

    rule_key = _parse_rule_key(recommendation_id)
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
            metadata=sanitized_metadata,
        )
    elif action == "escalate":
        detail = _apply_escalate(
            recommendation_id=recommendation_id,
            target_reviewer=target_reviewer,
            notes=notes,
            metadata=sanitized_metadata,
        )
    else:
        raise ValueError(f"Unsupported override action: {action}")

    detail.update(
        {
            "baseline_id": str(record.baseline_id) if record.baseline_id else None,
            "target_reviewer_id": str(record.target_reviewer_id)
            if record.target_reviewer_id
            else None,
            "execution_hash": execution_hash,
            "reversible": record.reversible,
        }
    )
    lineage_record = _persist_override_lineage(
        db,
        record,
        actor=actor,
        payload=lineage,
    )
    if lineage_record is not None:
        detail["lineage"] = _serialize_lineage(lineage_record)
    _persist_action(
        db,
        record,
        status="executed",
        detail=detail,
        execution_hash=execution_hash,
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


def reverse_override(
    db: Session,
    *,
    actor: models.User,
    recommendation_id: str,
    execution: models.ProtocolExecution,
    baseline: models.GovernanceBaselineVersion | None,
    notes: str | None,
    metadata: Dict[str, Any] | None = None,
) -> ActionResult:
    sanitized_metadata = _ensure_dict(metadata)
    execution_hash = _compute_execution_hash(
        recommendation_id=recommendation_id,
        actor_id=actor.id,
        action="reverse",
        status="reversed",
        execution_id=execution.id,
        baseline_id=getattr(baseline, "id", None),
        target_reviewer_id=None,
        metadata=sanitized_metadata,
    )
    existing = _get_action_by_hash(db, execution_hash=execution_hash)
    if existing is not None:
        return existing, dict(existing.detail_snapshot or {})

    record = (
        db.query(models.GovernanceOverrideAction)
        .filter(
            models.GovernanceOverrideAction.recommendation_id == recommendation_id,
            models.GovernanceOverrideAction.execution_id == execution.id,
        )
        .order_by(models.GovernanceOverrideAction.updated_at.desc())
        .first()
    )
    if record is None:
        raise ValueError("No override execution found to reverse")
    if record.status == "reversed":
        return record, dict(record.detail_snapshot or {})
    if record.status != "executed":
        raise ValueError("Only executed overrides can be reversed")
    if not record.reversible:
        raise ValueError("Override execution is not marked as reversible")

    baseline_context = baseline
    if baseline_context is None and record.baseline_id is not None:
        baseline_context = db.get(models.GovernanceBaselineVersion, record.baseline_id)

    stored_metadata = dict(record.meta or {})
    original_metadata = dict(stored_metadata)
    if sanitized_metadata:
        stored_metadata.setdefault("_reversal", {}).update(sanitized_metadata)
    record.meta = stored_metadata

    detail: Dict[str, Any]
    if record.action == "reassign":
        if baseline_context is None:
            raise ValueError("Reassign reversals require baseline context")
        detail = _reverse_reassign(
            db,
            actor=actor,
            recommendation_id=recommendation_id,
            baseline=baseline_context,
            target_reviewer_id=record.target_reviewer_id,
            notes=notes,
        )
    elif record.action == "cooldown":
        detail = _reverse_cooldown(
            db,
            actor=actor,
            recommendation_id=recommendation_id,
            execution=execution,
            baseline=baseline_context,
            notes=notes,
            metadata=original_metadata,
        )
    elif record.action == "escalate":
        detail = _reverse_escalate(
            recommendation_id=recommendation_id,
            target_reviewer_id=record.target_reviewer_id,
            notes=notes,
            metadata=original_metadata,
        )
    else:
        raise ValueError(f"Unsupported override action for reversal: {record.action}")

    detail.update(
        {
            "baseline_id": str(record.baseline_id) if record.baseline_id else None,
            "target_reviewer_id": str(record.target_reviewer_id)
            if record.target_reviewer_id
            else None,
            "execution_hash": execution_hash,
            "reversal": True,
            "reversal_notes": notes,
        }
    )
    if record.lineage is not None:
        detail["lineage"] = _serialize_lineage(record.lineage)
    if sanitized_metadata:
        detail["reversal_metadata"] = sanitized_metadata

    _persist_action(
        db,
        record,
        status="reversed",
        detail=detail,
        execution_hash=execution_hash,
    )

    rule_key = _parse_rule_key(recommendation_id, fallback=record.recommendation_id)
    record_governance_override_action_event(
        db,
        execution,
        recommendation_id=recommendation_id,
        rule_key=rule_key,
        action=record.action,
        status="reversed",
        actor=actor,
        detail=detail,
    )
    return record, detail


__all__ = [
    "accept_override",
    "decline_override",
    "execute_override",
    "reverse_override",
]
