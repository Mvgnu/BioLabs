"""Custody governance orchestration helpers."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, joinedload

from .. import models, notify, schemas

# purpose: orchestrate freezer custody governance analytics and lifecycle actions
# status: pilot
# depends_on: backend.app.models.GovernanceFreezerUnit, backend.app.models.GovernanceSampleCustodyLog
# related_docs: docs/operations/custody_governance.md

_DEPOSIT_ACTIONS = {"deposit", "placed", "returned", "received", "moved_in"}
_WITHDRAW_ACTIONS = {"withdrawn", "removed", "consumed", "disposed", "moved_out", "shipped"}

_ESCALATION_DEFAULT_SLA_MINUTES = {
    "critical": 15,
    "warning": 60,
    "info": 240,
}



def list_freezer_topology(
    db: Session,
    *,
    team_id: UUID | None = None,
) -> list[schemas.FreezerUnitTopology]:
    """Return freezer units with nested compartment occupancy summaries."""

    unit_query = db.query(models.GovernanceFreezerUnit)
    if team_id:
        unit_query = unit_query.filter(
            sa.or_(
                models.GovernanceFreezerUnit.team_id.is_(None),
                models.GovernanceFreezerUnit.team_id == team_id,
            )
        )
    units: list[models.GovernanceFreezerUnit] = (
        unit_query.order_by(models.GovernanceFreezerUnit.name.asc()).all()
    )
    if not units:
        return []

    compartment_ids: set[UUID] = set()
    for unit in units:
        for compartment in unit.compartments:
            compartment_ids.add(compartment.id)

    logs_by_compartment: dict[UUID, list[models.GovernanceSampleCustodyLog]] = defaultdict(list)
    if compartment_ids:
        logs: Iterable[models.GovernanceSampleCustodyLog] = (
            db.query(models.GovernanceSampleCustodyLog)
            .filter(models.GovernanceSampleCustodyLog.compartment_id.in_(compartment_ids))
            .order_by(models.GovernanceSampleCustodyLog.performed_at.desc())
            .all()
        )
        for log in logs:
            if log.compartment_id:
                logs_by_compartment[log.compartment_id].append(log)

    return [
        schemas.FreezerUnitTopology(
            id=unit.id,
            name=unit.name,
            status=unit.status,
            facility_code=unit.facility_code,
            guardrail_config=unit.guardrail_config or {},
            created_at=unit.created_at,
            updated_at=unit.updated_at,
            compartments=[
                _serialize_compartment(compartment, logs_by_compartment)
                for compartment in sorted(
                    unit.compartments, key=lambda c: c.position_index
                )
                if compartment.parent_id is None
            ],
        )
        for unit in units
    ]


def record_custody_event(
    db: Session,
    payload: schemas.SampleCustodyLogCreate,
    *,
    actor_id: UUID,
) -> models.GovernanceSampleCustodyLog:
    """Persist a custody log and evaluate guardrail heuristics."""

    now = datetime.now(timezone.utc)
    log = models.GovernanceSampleCustodyLog(
        asset_version_id=payload.asset_version_id,
        planner_session_id=payload.planner_session_id,
        protocol_execution_id=payload.protocol_execution_id,
        execution_event_id=payload.execution_event_id,
        compartment_id=payload.compartment_id,
        custody_action=payload.custody_action,
        quantity=payload.quantity,
        quantity_units=payload.quantity_units,
        performed_by_id=actor_id,
        performed_for_team_id=payload.performed_for_team_id,
        guardrail_flags=[],
        meta=payload.meta,
        notes=payload.notes,
        performed_at=payload.performed_at or now,
        created_at=now,
    )
    log.guardrail_flags = _evaluate_guardrails_for_log(db, log)
    db.add(log)
    db.flush()
    db.refresh(log)
    _attach_log_to_protocol(db, log)
    _synchronize_custody_escalations(db, log)
    return log


def fetch_custody_logs(
    db: Session,
    *,
    asset_id: UUID | None = None,
    asset_version_id: UUID | None = None,
    planner_session_id: UUID | None = None,
    protocol_execution_id: UUID | None = None,
    execution_event_id: UUID | None = None,
    compartment_id: UUID | None = None,
    limit: int = 100,
) -> list[models.GovernanceSampleCustodyLog]:
    """Retrieve custody ledger entries with filtering helpers."""

    query = db.query(models.GovernanceSampleCustodyLog)
    if asset_version_id:
        query = query.filter(models.GovernanceSampleCustodyLog.asset_version_id == asset_version_id)
    elif asset_id:
        query = query.join(models.DNAAssetVersion).filter(
            models.DNAAssetVersion.asset_id == asset_id
        )
    if planner_session_id:
        query = query.filter(
            models.GovernanceSampleCustodyLog.planner_session_id == planner_session_id
        )
    if protocol_execution_id:
        query = query.filter(
            models.GovernanceSampleCustodyLog.protocol_execution_id == protocol_execution_id
        )
    if execution_event_id:
        query = query.filter(
            models.GovernanceSampleCustodyLog.execution_event_id == execution_event_id
        )
    if compartment_id:
        query = query.filter(models.GovernanceSampleCustodyLog.compartment_id == compartment_id)
    return (
        query.order_by(models.GovernanceSampleCustodyLog.performed_at.desc())
        .limit(limit)
        .all()
    )


def _serialize_compartment(
    compartment: models.GovernanceFreezerCompartment,
    logs_by_compartment: dict[UUID, list[models.GovernanceSampleCustodyLog]],
) -> schemas.FreezerCompartmentNode:
    logs = logs_by_compartment.get(compartment.id, [])
    own_delta = sum(_resolve_quantity_delta(log) for log in logs)
    latest_activity = logs[0].performed_at if logs else None
    child_nodes = [
        _serialize_compartment(child, logs_by_compartment)
        for child in sorted(compartment.children, key=lambda c: c.position_index)
    ]
    occupancy = own_delta + sum(child.occupancy for child in child_nodes)
    guardrail_flags = _evaluate_guardrail_thresholds(compartment, occupancy)
    return schemas.FreezerCompartmentNode(
        id=compartment.id,
        label=compartment.label,
        position_index=compartment.position_index,
        capacity=compartment.capacity,
        guardrail_thresholds=compartment.guardrail_thresholds or {},
        occupancy=occupancy,
        guardrail_flags=guardrail_flags,
        latest_activity_at=latest_activity,
        children=child_nodes,
    )


def _attach_log_to_protocol(
    db: Session,
    log: models.GovernanceSampleCustodyLog,
) -> None:
    if not log.protocol_execution_id:
        return
    execution = db.get(models.ProtocolExecution, log.protocol_execution_id)
    if not execution:
        return
    governance_result = dict(execution.result or {})
    custody_payload = dict(governance_result.get("custody", {}))
    ledger = list(custody_payload.get("ledger", []))
    log_ref = {
        "log_id": str(log.id),
        "performed_at": log.performed_at.isoformat(),
        "custody_action": log.custody_action,
        "compartment_id": str(log.compartment_id) if log.compartment_id else None,
        "guardrail_flags": list(log.guardrail_flags or []),
    }
    if all(existing.get("log_id") != log_ref["log_id"] for existing in ledger):
        ledger.append(log_ref)
        custody_payload["ledger"] = ledger
        governance_result["custody"] = custody_payload
        execution.result = governance_result
        execution.updated_at = datetime.now(timezone.utc)
        db.add(execution)


def _resolve_quantity_delta(log: models.GovernanceSampleCustodyLog) -> int:
    quantity = log.quantity if log.quantity is not None else 1
    action = (log.custody_action or "").lower()
    if action in _WITHDRAW_ACTIONS:
        return -abs(quantity)
    if action in _DEPOSIT_ACTIONS:
        return abs(quantity)
    if log.quantity is not None:
        return log.quantity
    return 0


def _evaluate_guardrail_thresholds(
    compartment: models.GovernanceFreezerCompartment,
    occupancy: int,
) -> list[str]:
    flags: list[str] = []
    thresholds = compartment.guardrail_thresholds or {}
    capacity = compartment.capacity
    max_capacity = thresholds.get("max_capacity", capacity)
    min_capacity = thresholds.get("min_capacity")
    if max_capacity is not None and occupancy > max_capacity:
        flags.append("capacity.exceeded")
    if min_capacity is not None and occupancy < min_capacity:
        flags.append("capacity.depleted")
    if capacity and capacity > 0:
        utilization = occupancy / capacity
        critical_ratio = thresholds.get("critical_utilization")
        if critical_ratio is not None and utilization > critical_ratio:
            flags.append("utilization.critical")
    return flags


def list_custody_escalations(
    db: Session,
    *,
    team_id: UUID | None = None,
    statuses: Sequence[str] | None = None,
    protocol_execution_id: UUID | None = None,
    execution_event_id: UUID | None = None,
) -> list[models.GovernanceCustodyEscalation]:
    """Return custody escalations filtered by team and status."""

    query = db.query(models.GovernanceCustodyEscalation).options(
        joinedload(models.GovernanceCustodyEscalation.protocol_execution).joinedload(
            models.ProtocolExecution.template
        )
    )
    query = query.outerjoin(
        models.GovernanceFreezerUnit,
        models.GovernanceFreezerUnit.id
        == models.GovernanceCustodyEscalation.freezer_unit_id,
    ).outerjoin(
        models.GovernanceSampleCustodyLog,
        models.GovernanceSampleCustodyLog.id
        == models.GovernanceCustodyEscalation.log_id,
    )
    if statuses:
        query = query.filter(models.GovernanceCustodyEscalation.status.in_(statuses))
    if team_id:
        query = query.filter(
            sa.or_(
                models.GovernanceFreezerUnit.team_id == team_id,
                models.GovernanceSampleCustodyLog.performed_for_team_id == team_id,
            )
        )
    if protocol_execution_id:
        query = query.filter(
            models.GovernanceCustodyEscalation.protocol_execution_id
            == protocol_execution_id
        )
    if execution_event_id:
        query = query.filter(
            models.GovernanceCustodyEscalation.execution_event_id == execution_event_id
        )
    return (
        query.order_by(models.GovernanceCustodyEscalation.due_at.asc()).all()
    )


def acknowledge_custody_escalation(
    db: Session,
    escalation_id: UUID,
    *,
    actor_id: UUID,
) -> models.GovernanceCustodyEscalation | None:
    """Mark a custody escalation as acknowledged by an operator."""

    escalation = db.get(models.GovernanceCustodyEscalation, escalation_id)
    if not escalation:
        return None
    now = datetime.now(timezone.utc)
    escalation.status = "acknowledged"
    escalation.acknowledged_at = now
    escalation.assigned_to_id = actor_id
    escalation.updated_at = now
    _ensure_recovery_drill(escalation, now)
    _sync_protocol_escalation_state(db, escalation)
    db.add(escalation)
    db.flush()
    return escalation


def resolve_custody_escalation(
    db: Session,
    escalation_id: UUID,
    *,
    actor_id: UUID | None = None,
) -> models.GovernanceCustodyEscalation | None:
    """Resolve an open custody escalation."""

    escalation = db.get(models.GovernanceCustodyEscalation, escalation_id)
    if not escalation:
        return None
    now = datetime.now(timezone.utc)
    escalation.status = "resolved"
    escalation.resolved_at = now
    if actor_id:
        escalation.assigned_to_id = actor_id
    escalation.updated_at = now
    _ensure_recovery_drill(escalation, now)
    _sync_protocol_escalation_state(db, escalation)
    db.add(escalation)
    db.flush()
    return escalation


def trigger_custody_escalation_notifications(
    db: Session,
    escalation_id: UUID,
) -> models.GovernanceCustodyEscalation | None:
    """Dispatch notification hooks for the supplied escalation."""

    escalation = db.get(models.GovernanceCustodyEscalation, escalation_id)
    if not escalation:
        return None
    _dispatch_custody_escalation_notifications(db, escalation)
    return escalation


def list_freezer_faults(
    db: Session,
    *,
    team_id: UUID | None = None,
    include_resolved: bool = False,
) -> list[models.GovernanceFreezerFault]:
    """Return freezer faults to power governance dashboards."""

    query = db.query(models.GovernanceFreezerFault).join(
        models.GovernanceFreezerUnit,
        models.GovernanceFreezerUnit.id == models.GovernanceFreezerFault.freezer_unit_id,
    )
    if team_id:
        query = query.filter(models.GovernanceFreezerUnit.team_id == team_id)
    if not include_resolved:
        query = query.filter(models.GovernanceFreezerFault.resolved_at.is_(None))
    return (
        query.order_by(models.GovernanceFreezerFault.occurred_at.desc()).all()
    )


def record_freezer_fault(
    db: Session,
    freezer: models.GovernanceFreezerUnit,
    *,
    compartment_id: UUID | None,
    fault_type: str,
    severity: str,
    guardrail_flag: str | None = None,
    meta: dict[str, object] | None = None,
) -> models.GovernanceFreezerFault:
    """Persist a freezer fault entry."""

    now = datetime.now(timezone.utc)
    fault = models.GovernanceFreezerFault(
        freezer_unit_id=freezer.id,
        compartment_id=compartment_id,
        fault_type=fault_type,
        severity=severity,
        guardrail_flag=guardrail_flag,
        occurred_at=now,
        meta=meta or {},
        created_at=now,
    )
    db.add(fault)
    db.flush()
    return fault


def resolve_freezer_fault(
    db: Session,
    fault_id: UUID,
) -> models.GovernanceFreezerFault | None:
    """Mark a freezer fault as resolved."""

    fault = db.get(models.GovernanceFreezerFault, fault_id)
    if not fault:
        return None
    fault.resolved_at = datetime.now(timezone.utc)
    db.add(fault)
    db.flush()
    return fault


def _synchronize_custody_escalations(
    db: Session,
    log: models.GovernanceSampleCustodyLog,
) -> None:
    guardrail_flags = log.guardrail_flags or []
    if guardrail_flags:
        _upsert_custody_escalation(db, log, guardrail_flags)
        _record_faults_from_log(db, log, guardrail_flags)
    else:
        _resolve_existing_escalations(db, log)


def _upsert_custody_escalation(
    db: Session,
    log: models.GovernanceSampleCustodyLog,
    guardrail_flags: Sequence[str],
) -> None:
    severity = _determine_escalation_severity(guardrail_flags)
    if severity is None:
        return
    reason = _build_escalation_reason(log, guardrail_flags)
    due_at = _compute_sla_due_at(log, severity)
    existing = (
        db.query(models.GovernanceCustodyEscalation)
        .filter(models.GovernanceCustodyEscalation.status == "open")
        .filter(models.GovernanceCustodyEscalation.compartment_id == log.compartment_id)
        .filter(models.GovernanceCustodyEscalation.severity == severity)
        .order_by(models.GovernanceCustodyEscalation.created_at.desc())
        .first()
    )
    now = datetime.now(timezone.utc)
    flags = sorted(set(guardrail_flags))
    if existing:
        existing.reason = reason
        existing.guardrail_flags = flags
        existing.due_at = due_at
        existing.protocol_execution_id = log.protocol_execution_id
        existing.execution_event_id = log.execution_event_id
        existing.meta = {
            **(existing.meta or {}),
            "last_log_id": str(log.id),
            "protocol_execution_id": str(log.protocol_execution_id)
            if log.protocol_execution_id
            else None,
        }
        existing.updated_at = now
        escalation = existing
    else:
        escalation = models.GovernanceCustodyEscalation(
            log_id=log.id,
            freezer_unit_id=log.compartment.freezer_id if log.compartment else None,
            compartment_id=log.compartment_id,
            asset_version_id=log.asset_version_id,
            protocol_execution_id=log.protocol_execution_id,
            execution_event_id=log.execution_event_id,
            severity=severity,
            status="open",
            reason=reason,
            due_at=due_at,
            guardrail_flags=flags,
            meta={
                "last_log_id": str(log.id),
                "team_id": str(log.performed_for_team_id)
                if log.performed_for_team_id
                else None,
                "protocol_execution_id": str(log.protocol_execution_id)
                if log.protocol_execution_id
                else None,
            },
            created_at=now,
        )
        db.add(escalation)
    _ensure_recovery_drill(escalation, now)
    db.flush()
    _sync_protocol_escalation_state(db, escalation)
    _dispatch_custody_escalation_notifications(db, escalation)


def _resolve_existing_escalations(
    db: Session,
    log: models.GovernanceSampleCustodyLog,
) -> None:
    query = (
        db.query(models.GovernanceCustodyEscalation)
        .filter(models.GovernanceCustodyEscalation.status == "open")
        .filter(models.GovernanceCustodyEscalation.compartment_id == log.compartment_id)
    )
    now = datetime.now(timezone.utc)
    for escalation in query:
        escalation.status = "resolved"
        escalation.resolved_at = now
        escalation.meta = {
            **(escalation.meta or {}),
            "resolved_by_log_id": str(log.id),
        }
        escalation.updated_at = now
        db.add(escalation)
        _ensure_recovery_drill(escalation, now)
        _sync_protocol_escalation_state(db, escalation)
    db.flush()


def _determine_escalation_severity(flags: Sequence[str]) -> str | None:
    if not flags:
        return None
    if any(flag.startswith("capacity.") for flag in flags):
        return "critical"
    if any(flag.startswith("compartment.") for flag in flags):
        return "critical"
    if any(flag in {"occupancy.stale", "lineage.required"} for flag in flags):
        return "warning"
    if any(flag == "lineage.unlinked" for flag in flags):
        return "info"
    return "warning"


def _ensure_recovery_drill(
    escalation: models.GovernanceCustodyEscalation,
    now: datetime,
) -> None:
    meta = dict(escalation.meta or {})
    due_at = escalation.due_at
    if due_at and due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=timezone.utc)
    if due_at and due_at <= now and not meta.get("recovery_drill_open"):
        meta["recovery_drill_open"] = True
        meta.setdefault("recovery_opened_at", now.isoformat())
    if escalation.status == "resolved" and meta.get("recovery_drill_open"):
        meta["recovery_drill_open"] = False
        meta["recovery_closed_at"] = now.isoformat()
    escalation.meta = meta


def _sync_protocol_escalation_state(
    db: Session,
    escalation: models.GovernanceCustodyEscalation,
) -> None:
    if not escalation.protocol_execution_id:
        return
    execution = db.get(models.ProtocolExecution, escalation.protocol_execution_id)
    if not execution:
        return
    governance_result = dict(execution.result or {})
    custody_payload = dict(governance_result.get("custody", {}))
    escalation_map = dict(custody_payload.get("escalations", {}))
    escalation_map[str(escalation.id)] = {
        "status": escalation.status,
        "severity": escalation.severity,
        "reason": escalation.reason,
        "due_at": escalation.due_at.isoformat() if escalation.due_at else None,
        "acknowledged_at": escalation.acknowledged_at.isoformat()
        if escalation.acknowledged_at
        else None,
        "resolved_at": escalation.resolved_at.isoformat() if escalation.resolved_at else None,
        "guardrail_flags": list(escalation.guardrail_flags or []),
        "recovery_drill_open": (escalation.meta or {}).get("recovery_drill_open"),
    }
    custody_payload["escalations"] = escalation_map
    governance_result["custody"] = custody_payload
    execution.result = governance_result
    execution.updated_at = datetime.now(timezone.utc)
    db.add(execution)


def _compute_sla_due_at(
    log: models.GovernanceSampleCustodyLog,
    severity: str,
) -> datetime:
    now = datetime.now(timezone.utc)
    minutes = _ESCALATION_DEFAULT_SLA_MINUTES.get(severity, 240)
    freezer_config = {}
    if log.compartment and log.compartment.freezer:
        freezer_config = log.compartment.freezer.guardrail_config or {}
    compartment_config = log.compartment.guardrail_thresholds if log.compartment else {}
    escalation_config = {}
    if freezer_config:
        escalation_config.update(freezer_config.get("escalation", {}))
    if compartment_config:
        compartment_escalation = compartment_config.get("escalation", {})
        if isinstance(compartment_escalation, dict):
            escalation_config.update(compartment_escalation)
        minutes = compartment_config.get(f"{severity}_sla_minutes", minutes)
    minutes = escalation_config.get(f"{severity}_sla_minutes", minutes)
    return now + timedelta(minutes=minutes)


def _build_escalation_reason(
    log: models.GovernanceSampleCustodyLog,
    flags: Sequence[str],
) -> str:
    flag_summary = ", ".join(sorted(flags))
    base = f"Guardrail escalation detected: {flag_summary}"
    if log.compartment:
        return f"{base} in compartment {log.compartment.label}"
    return base


def _dispatch_custody_escalation_notifications(
    db: Session,
    escalation: models.GovernanceCustodyEscalation,
) -> None:
    recipients = _resolve_escalation_recipients(db, escalation)
    if not recipients:
        return
    existing = {
        entry.get("recipient")
        for entry in (escalation.notifications or [])
        if entry.get("recipient")
    }
    severity = escalation.severity or "warning"
    sent_records = list(escalation.notifications or [])
    now = datetime.now(timezone.utc)
    for user in recipients:
        if not user.email or user.email in existing:
            continue
        subject = f"Custody escalation: {escalation.reason}"
        message = (
            f"A custody escalation ({severity}) is pending for compartment"
            f" {escalation.compartment_id or 'unassigned'} with due"
            f" at {escalation.due_at.isoformat() if escalation.due_at else 'unspecified'}."
        )
        notify.send_email(user.email, subject, message)
        sent_records.append(
            {
                "recipient": user.email,
                "channel": "email",
                "sent_at": now.isoformat(),
            }
        )
        notification = models.Notification(
            user_id=user.id,
            title="Custody escalation",
            message=escalation.reason,
            category="governance",
            priority="urgent" if severity == "critical" else "high",
            meta={
                "escalation_id": str(escalation.id),
                "due_at": escalation.due_at.isoformat()
                if escalation.due_at
                else None,
            },
        )
        db.add(notification)
    escalation.notifications = sent_records
    escalation.updated_at = now
    db.add(escalation)
    db.flush()


def _resolve_escalation_recipients(
    db: Session,
    escalation: models.GovernanceCustodyEscalation,
) -> list[models.User]:
    recipients: dict[UUID, models.User] = {}
    freezer = escalation.freezer
    if not freezer and escalation.freezer_unit_id:
        freezer = db.get(models.GovernanceFreezerUnit, escalation.freezer_unit_id)
    if freezer and freezer.team_id:
        members = (
            db.query(models.TeamMember)
            .filter(models.TeamMember.team_id == freezer.team_id)
            .all()
        )
        for member in members:
            if member.user and member.user.email:
                recipients[member.user.id] = member.user
    if escalation.log and escalation.log.actor and escalation.log.actor.email:
        recipients[escalation.log.actor.id] = escalation.log.actor
    return list(recipients.values())


def _record_faults_from_log(
    db: Session,
    log: models.GovernanceSampleCustodyLog,
    guardrail_flags: Sequence[str],
) -> None:
    if not log.compartment or not log.compartment.freezer:
        return
    freezer = log.compartment.freezer
    fault_flags = [flag for flag in guardrail_flags if flag.startswith("fault.")]
    if log.meta:
        fault_meta = log.meta.get("fault_flags") or []
        fault_flags.extend(flag for flag in fault_meta if isinstance(flag, str))
    recorded = set()
    for flag in fault_flags:
        fault_type = flag.split(".", 1)[-1] if "." in flag else flag
        key = (fault_type, log.compartment_id)
        if key in recorded:
            continue
        recorded.add(key)
        record_freezer_fault(
            db,
            freezer,
            compartment_id=log.compartment_id,
            fault_type=fault_type,
            severity="critical"
            if "critical" in fault_type or "temperature" in fault_type
            else "warning",
            guardrail_flag=flag,
            meta={
                "log_id": str(log.id),
                "asset_version_id": str(log.asset_version_id)
                if log.asset_version_id
                else None,
            },
        )



def _evaluate_guardrails_for_log(
    db: Session,
    log: models.GovernanceSampleCustodyLog,
) -> list[str]:
    if not log.compartment_id:
        return []
    compartment = db.get(models.GovernanceFreezerCompartment, log.compartment_id)
    if not compartment:
        return ["compartment.missing"]
    existing_logs: list[models.GovernanceSampleCustodyLog] = (
        db.query(models.GovernanceSampleCustodyLog)
        .filter(models.GovernanceSampleCustodyLog.compartment_id == log.compartment_id)
        .order_by(models.GovernanceSampleCustodyLog.performed_at.asc())
        .all()
    )
    occupancy = sum(_resolve_quantity_delta(entry) for entry in existing_logs)
    occupancy += _resolve_quantity_delta(log)
    flags = _evaluate_guardrail_thresholds(compartment, occupancy)
    thresholds = compartment.guardrail_thresholds or {}
    if log.asset_version_id is None and log.planner_session_id is None:
        flags.append("lineage.unlinked")
    if thresholds.get("lineage_required") and (
        log.asset_version_id is None or log.planner_session_id is None
    ):
        flags.append("lineage.required")
    if thresholds.get("stale_minutes") and existing_logs:
        latest_activity = existing_logs[-1].performed_at
        delta = log.performed_at - latest_activity
        if delta.total_seconds() / 60 > thresholds["stale_minutes"]:
            flags.append("occupancy.stale")
    meta_flags: Sequence[str] = ()
    if log.meta:
        meta_flags = log.meta.get("guardrail_flags", []) or []
    for flag in meta_flags:
        if flag not in flags:
            flags.append(flag)
    return flags
