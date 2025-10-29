"""API routes for custody and freezer governance."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..services import sample_governance

# purpose: expose custody governance endpoints for freezer topology and ledger actions
# status: pilot
# depends_on: backend.app.services.sample_governance

router = APIRouter(prefix="/api/governance/custody", tags=["governance", "custody"])


def _require_operator(user: models.User) -> None:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Custody governance access requires administrator privileges",
        )


@router.get("/freezers", response_model=list[schemas.FreezerUnitTopology])
def get_freezer_topology(
    team_id: UUID | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _require_operator(user)
    return sample_governance.list_freezer_topology(db, team_id=team_id)


@router.get("/logs", response_model=list[schemas.SampleCustodyLogOut])
def list_custody_logs(
    asset_id: UUID | None = None,
    asset_version_id: UUID | None = None,
    planner_session_id: UUID | None = None,
    protocol_execution_id: UUID | None = None,
    execution_event_id: UUID | None = None,
    compartment_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _require_operator(user)
    logs = sample_governance.fetch_custody_logs(
        db,
        asset_id=asset_id,
        asset_version_id=asset_version_id,
        planner_session_id=planner_session_id,
        protocol_execution_id=protocol_execution_id,
        execution_event_id=execution_event_id,
        compartment_id=compartment_id,
        limit=limit,
    )
    return logs


@router.post(
    "/logs",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.SampleCustodyLogOut,
)
def create_custody_log(
    entry: schemas.SampleCustodyLogCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _require_operator(user)
    log = sample_governance.record_custody_event(db, entry, actor_id=user.id)
    db.refresh(log)
    db.commit()
    return log


@router.get(
    "/escalations",
    response_model=list[schemas.CustodyEscalation],
)
def list_custody_escalations(
    team_id: UUID | None = None,
    status_filters: list[str] | None = Query(default=None, alias="status"),
    protocol_execution_id: UUID | None = None,
    execution_event_id: UUID | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _require_operator(user)
    escalations = sample_governance.list_custody_escalations(
        db,
        team_id=team_id,
        statuses=status_filters,
        protocol_execution_id=protocol_execution_id,
        execution_event_id=execution_event_id,
    )
    return escalations


@router.get(
    "/protocols",
    response_model=list[schemas.CustodyProtocolExecution],
)
def list_protocol_guardrail_snapshots(
    guardrail_status: list[str] | None = Query(default=None, alias="status"),
    has_open_drill: bool | None = Query(default=None),
    severity: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _require_operator(user)
    executions = sample_governance.list_protocol_guardrail_executions(
        db,
        guardrail_statuses=guardrail_status,
        has_open_drill=has_open_drill,
        severity=severity,
        limit=limit,
    )
    return executions


@router.post(
    "/escalations/{escalation_id}/acknowledge",
    response_model=schemas.CustodyEscalationAck,
)
def acknowledge_custody_escalation(
    escalation_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _require_operator(user)
    escalation = sample_governance.acknowledge_custody_escalation(
        db,
        escalation_id,
        actor_id=user.id,
    )
    if not escalation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escalation not found")
    db.commit()
    return schemas.CustodyEscalationAck(
        acknowledged_at=escalation.acknowledged_at,
        status=escalation.status,
    )


@router.post(
    "/escalations/{escalation_id}/resolve",
    response_model=schemas.CustodyEscalation,
)
def resolve_custody_escalation(
    escalation_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _require_operator(user)
    escalation = sample_governance.resolve_custody_escalation(
        db,
        escalation_id,
        actor_id=user.id,
    )
    if not escalation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escalation not found")
    db.refresh(escalation)
    db.commit()
    return escalation


@router.post(
    "/escalations/{escalation_id}/notify",
    response_model=schemas.CustodyEscalation,
)
def trigger_escalation_notifications(
    escalation_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _require_operator(user)
    escalation = sample_governance.trigger_custody_escalation_notifications(db, escalation_id)
    if not escalation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Escalation not found")
    db.refresh(escalation)
    db.commit()
    return escalation


@router.get(
    "/faults",
    response_model=list[schemas.FreezerFault],
)
def list_freezer_faults(
    team_id: UUID | None = None,
    include_resolved: bool = Query(default=False),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _require_operator(user)
    faults = sample_governance.list_freezer_faults(
        db,
        team_id=team_id,
        include_resolved=include_resolved,
    )
    return faults


@router.post(
    "/freezers/{freezer_id}/faults",
    response_model=schemas.FreezerFault,
    status_code=status.HTTP_201_CREATED,
)
def create_freezer_fault(
    freezer_id: UUID,
    payload: schemas.FreezerFaultCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _require_operator(user)
    freezer = db.get(models.GovernanceFreezerUnit, freezer_id)
    if not freezer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Freezer not found")
    fault = sample_governance.record_freezer_fault(
        db,
        freezer,
        compartment_id=payload.compartment_id,
        fault_type=payload.fault_type,
        severity=payload.severity,
        guardrail_flag=payload.guardrail_flag,
        meta=payload.meta,
    )
    db.refresh(fault)
    db.commit()
    return fault


@router.post(
    "/faults/{fault_id}/resolve",
    response_model=schemas.FreezerFault,
)
def resolve_freezer_fault(
    fault_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _require_operator(user)
    fault = sample_governance.resolve_freezer_fault(db, fault_id)
    if not fault:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fault not found")
    db.refresh(fault)
    db.commit()
    return fault
