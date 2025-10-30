"""Instrumentation orchestration API routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..rbac import check_team_role
from ..services import instrumentation

# purpose: expose robotic lab scheduling, run control, and telemetry endpoints
# status: pilot
# depends_on: backend.app.services.instrumentation

router = APIRouter(prefix="/api/instrumentation", tags=["instrumentation", "automation"])


@router.get("/instruments", response_model=list[schemas.InstrumentProfile])
def list_instruments(
    team_id: UUID | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if team_id:
        check_team_role(db, user, team_id, ["member", "manager", "owner"])
    profiles = instrumentation.list_instrument_profiles(db, team_id=team_id)
    return profiles


@router.post(
    "/instruments/{equipment_id}/reservations",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.InstrumentReservationOut,
)
def create_reservation(
    equipment_id: UUID,
    payload: schemas.InstrumentReservationCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    team_scope = payload.team_id or _resolve_equipment_team(db, equipment_id)
    if team_scope:
        check_team_role(db, user, team_scope, ["member", "manager", "owner"])
    try:
        reservation = instrumentation.schedule_reservation(
            db,
            equipment_id,
            payload,
            actor_id=user.id,
        )
        db.commit()
        db.refresh(reservation)
    except instrumentation.ReservationConflict as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except instrumentation.InstrumentNotFound as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return reservation


@router.post(
    "/instruments/{equipment_id}/simulate",
    response_model=schemas.InstrumentSimulationResult,
)
def simulate_instrument(
    equipment_id: UUID,
    payload: schemas.InstrumentSimulationRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    team_scope = payload.team_id or _resolve_equipment_team(db, equipment_id)
    if team_scope:
        check_team_role(db, user, team_scope, ["member", "manager", "owner"])
    try:
        result = instrumentation.simulate_run(
            db,
            equipment_id,
            payload,
            actor_id=user.id,
        )
        db.commit()
        return result
    except instrumentation.InstrumentationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except instrumentation.InstrumentNotFound as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post(
    "/instruments/{equipment_id}/capabilities",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.InstrumentCapabilityOut,
)
def create_capability(
    equipment_id: UUID,
    payload: schemas.InstrumentCapabilityCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    team_scope = _resolve_equipment_team(db, equipment_id)
    if team_scope:
        check_team_role(db, user, team_scope, ["manager", "owner"])
    try:
        capability = instrumentation.register_capability(db, equipment_id, payload)
        db.commit()
        db.refresh(capability)
    except instrumentation.InstrumentNotFound as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except instrumentation.CapabilityConflict as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return capability


@router.post(
    "/instruments/{equipment_id}/sops",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.InstrumentSOPSummary,
)
def link_sop(
    equipment_id: UUID,
    payload: schemas.InstrumentSOPLinkCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    team_scope = _resolve_equipment_team(db, equipment_id)
    if team_scope:
        check_team_role(db, user, team_scope, ["manager", "owner"])
    try:
        link = instrumentation.link_sop(db, equipment_id, payload)
        db.commit()
        db.refresh(link)
    except instrumentation.InstrumentNotFound as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except instrumentation.SOPNotFound as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return schemas.InstrumentSOPSummary(
        sop_id=link.sop_id,
        title=link.sop.title if link.sop else "",
        version=link.sop.version if link.sop else 0,
        status=link.status,
        effective_at=link.effective_at,
        retired_at=link.retired_at,
    )


@router.post(
    "/reservations/{reservation_id}/dispatch",
    response_model=schemas.InstrumentRunOut,
)
def dispatch_reservation(
    reservation_id: UUID,
    payload: schemas.InstrumentRunDispatch,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    reservation = db.get(models.InstrumentRunReservation, reservation_id)
    if not reservation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reservation not found")
    team_scope = reservation.team_id or _resolve_equipment_team(db, reservation.equipment_id)
    if team_scope:
        check_team_role(db, user, team_scope, ["member", "manager", "owner"])
    try:
        run = instrumentation.dispatch_run(db, reservation_id, payload)
        db.commit()
        db.refresh(run)
    except instrumentation.GuardrailViolation as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except instrumentation.ReservationConflict as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return run


@router.post(
    "/runs/{run_id}/status",
    response_model=schemas.InstrumentRunOut,
)
def update_run_status(
    run_id: UUID,
    payload: schemas.InstrumentRunStatusUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    run = db.get(models.InstrumentRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    team_scope = run.team_id or _resolve_equipment_team(db, run.equipment_id)
    if team_scope:
        check_team_role(db, user, team_scope, ["member", "manager", "owner"])
    try:
        run = instrumentation.update_run_status(db, run_id, payload)
        db.commit()
        db.refresh(run)
    except instrumentation.InstrumentNotFound as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return run


@router.post(
    "/runs/{run_id}/telemetry",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.InstrumentTelemetrySampleOut,
)
def create_telemetry_sample(
    run_id: UUID,
    payload: schemas.InstrumentTelemetrySampleCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    run = db.get(models.InstrumentRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    team_scope = run.team_id or _resolve_equipment_team(db, run.equipment_id)
    if team_scope:
        check_team_role(db, user, team_scope, ["member", "manager", "owner"])
    try:
        sample = instrumentation.record_telemetry_sample(db, run_id, payload)
        db.commit()
        db.refresh(sample)
    except instrumentation.GuardrailViolation as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except instrumentation.InstrumentNotFound as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return sample


@router.get("/runs", response_model=list[schemas.InstrumentRunOut])
def list_runs(
    equipment_id: UUID | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if equipment_id:
        team_scope = _resolve_equipment_team(db, equipment_id)
        if team_scope:
            check_team_role(db, user, team_scope, ["member", "manager", "owner"])
    runs = instrumentation.list_runs(
        db,
        equipment_id=equipment_id,
        status=status_filter,
        limit=limit,
    )
    return [schemas.InstrumentRunOut.model_validate(run) for run in runs]


@router.get(
    "/runs/{run_id}/telemetry",
    response_model=schemas.InstrumentRunTelemetryEnvelope,
)
def get_run_telemetry(
    run_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    run = db.get(models.InstrumentRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    team_scope = run.team_id or _resolve_equipment_team(db, run.equipment_id)
    if team_scope:
        check_team_role(db, user, team_scope, ["member", "manager", "owner"])
    try:
        return instrumentation.load_run_envelope(db, run_id)
    except instrumentation.InstrumentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


def _resolve_equipment_team(db: Session, equipment_id: UUID) -> UUID | None:
    equipment = db.get(models.Equipment, equipment_id)
    return equipment.team_id if equipment else None
