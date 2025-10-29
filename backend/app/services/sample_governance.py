"""Custody governance orchestration helpers."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from .. import models, schemas

# purpose: orchestrate freezer custody governance analytics and lifecycle actions
# status: pilot
# depends_on: backend.app.models.GovernanceFreezerUnit, backend.app.models.GovernanceSampleCustodyLog
# related_docs: docs/operations/custody_governance.md

_DEPOSIT_ACTIONS = {"deposit", "placed", "returned", "received", "moved_in"}
_WITHDRAW_ACTIONS = {"withdrawn", "removed", "consumed", "disposed", "moved_out", "shipped"}


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
    return log


def fetch_custody_logs(
    db: Session,
    *,
    asset_id: UUID | None = None,
    asset_version_id: UUID | None = None,
    planner_session_id: UUID | None = None,
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
    if log.asset_version_id is None and log.planner_session_id is None:
        flags.append("lineage.unlinked")
    return flags
