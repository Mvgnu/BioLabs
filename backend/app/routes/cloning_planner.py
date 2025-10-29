"""Cloning planner API routes."""

# purpose: expose cloning planner session orchestration endpoints
# status: experimental
# depends_on: backend.app.services.cloning_planner, backend.app.schemas

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..services import cloning_planner
from ..tasks import celery_app

router = APIRouter(prefix="/api/cloning-planner", tags=["cloning-planner"])


@router.post("/sessions", response_model=schemas.CloningPlannerSessionOut, status_code=status.HTTP_201_CREATED)
def create_cloning_planner_session(
    payload: schemas.CloningPlannerSessionCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.CloningPlannerSessionOut:
    """Create a new cloning planner session."""

    # purpose: allow operators to bootstrap cloning planner workflows via API
    planner = cloning_planner.create_session(
        db,
        created_by=user,
        assembly_strategy=payload.assembly_strategy,
        input_sequences=[sequence.model_dump() for sequence in payload.input_sequences],
        metadata=payload.metadata or {},
    )
    db.commit()
    db.refresh(planner)
    cloning_planner.enqueue_pipeline(planner.id)
    db.refresh(planner)
    serialised = cloning_planner.serialize_session(planner)
    return schemas.CloningPlannerSessionOut(**serialised)


@router.get("/sessions/{session_id}", response_model=schemas.CloningPlannerSessionOut)
def get_cloning_planner_session(
    session_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.CloningPlannerSessionOut:
    """Fetch a cloning planner session by identifier."""

    # purpose: retrieve planner progress for dashboards and wizard resume flows
    planner = (
        db.query(models.CloningPlannerSession)
        .filter(models.CloningPlannerSession.id == session_id)
        .first()
    )
    if not planner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planner session not found")
    if planner.created_by_id not in {None, user.id} and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to planner session denied")
    return schemas.CloningPlannerSessionOut(**cloning_planner.serialize_session(planner))


@router.post("/sessions/{session_id}/resume", response_model=schemas.CloningPlannerSessionOut)
def resume_cloning_planner_session(
    session_id: UUID,
    payload: schemas.CloningPlannerResumeRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.CloningPlannerSessionOut:
    """Resume a cloning planner session from the last checkpoint."""

    # purpose: restart Celery orchestration with optional override payloads
    planner = (
        db.query(models.CloningPlannerSession)
        .filter(models.CloningPlannerSession.id == session_id)
        .first()
    )
    if not planner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planner session not found")
    if planner.created_by_id not in {None, user.id} and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to planner session denied")
    overrides = payload.overrides or {}
    resume_step = (payload.step or planner.current_step or "primers").lower()
    product_size_range = overrides.get("product_size_range")
    size_range: tuple[int, int] | None = None
    if product_size_range and len(product_size_range) == 2:
        size_range = (int(product_size_range[0]), int(product_size_range[1]))
    task_id = cloning_planner.enqueue_pipeline(
        planner.id,
        product_size_range=size_range,
        target_tm=overrides.get("target_tm"),
        enzymes=overrides.get("enzymes"),
        chromatograms=overrides.get("chromatograms"),
        resume_from=resume_step,
    )
    db.refresh(planner)
    serialised = cloning_planner.serialize_session(planner)
    if task_id and not serialised.get("celery_task_id"):
        serialised["celery_task_id"] = task_id
    return schemas.CloningPlannerSessionOut(**serialised)


@router.post("/sessions/{session_id}/cancel", response_model=schemas.CloningPlannerSessionOut)
def cancel_cloning_planner_session(
    session_id: UUID,
    payload: schemas.CloningPlannerCancelRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.CloningPlannerSessionOut:
    """Cancel a cloning planner session and revoke outstanding tasks."""

    # purpose: surface guardrail-aware cancellation checkpoints for operators
    planner = (
        db.query(models.CloningPlannerSession)
        .filter(models.CloningPlannerSession.id == session_id)
        .first()
    )
    if not planner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planner session not found")
    if planner.created_by_id not in {None, user.id} and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to planner session denied")
    if planner.celery_task_id:
        celery_app.control.revoke(planner.celery_task_id, terminate=True)
    now = datetime.now(timezone.utc)
    timings = dict(planner.stage_timings or {})
    current_step = planner.current_step or "primers"
    entry = dict(timings.get(current_step) or {})
    entry.update(
        {
            "status": "cancelled",
            "completed_at": now.isoformat(),
            "error": payload.reason,
        }
    )
    timings[current_step] = entry
    planner.stage_timings = timings
    planner.status = "cancelled"
    planner.last_error = payload.reason
    planner.updated_at = now
    planner.celery_task_id = None
    db.add(planner)
    db.commit()
    db.refresh(planner)
    return schemas.CloningPlannerSessionOut(**cloning_planner.serialize_session(planner))


@router.post("/sessions/{session_id}/steps/{step}", response_model=schemas.CloningPlannerSessionOut)
def record_cloning_planner_stage(
    session_id: UUID,
    step: str,
    payload: schemas.CloningPlannerStageRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.CloningPlannerSessionOut:
    """Persist stage outputs for a cloning planner session."""

    # purpose: update planner state as operators or background tasks complete stages
    planner = (
        db.query(models.CloningPlannerSession)
        .filter(models.CloningPlannerSession.id == session_id)
        .first()
    )
    if not planner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planner session not found")
    if planner.created_by_id not in {None, user.id} and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to planner session denied")
    config = payload.payload or {}
    try:
        normalised_step = step.lower()
        if normalised_step == "primers":
            product_size_range = config.get("product_size_range")
            if product_size_range and len(product_size_range) == 2:
                size_range = (int(product_size_range[0]), int(product_size_range[1]))
            else:
                size_range = None
            updated = cloning_planner.run_primer_design(
                db,
                planner=planner,
                product_size_range=size_range,
                target_tm=config.get("target_tm"),
            )
        elif normalised_step == "restriction":
            updated = cloning_planner.run_restriction_analysis(
                db,
                planner=planner,
                enzymes=config.get("enzymes"),
            )
        elif normalised_step == "assembly":
            updated = cloning_planner.run_assembly_planning(
                db,
                planner=planner,
                strategy=config.get("strategy"),
            )
        elif normalised_step == "qc":
            updated = cloning_planner.run_qc_checks(
                db,
                planner=planner,
                chromatograms=config.get("chromatograms"),
            )
        else:
            updated = cloning_planner.record_stage_progress(
                db,
                planner=planner,
                step=step,
                payload=config,
                next_step=payload.next_step,
                status=payload.status,
                guardrail_state=payload.guardrail_state,
                task_id=payload.task_id,
                error=payload.error,
            )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    db.commit()
    db.refresh(updated)
    return schemas.CloningPlannerSessionOut(**cloning_planner.serialize_session(updated))


@router.post("/sessions/{session_id}/finalize", response_model=schemas.CloningPlannerSessionOut)
def finalize_cloning_planner_session(
    session_id: UUID,
    payload: schemas.CloningPlannerFinalizeRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.CloningPlannerSessionOut:
    """Finalize a cloning planner session after guardrail checks pass."""

    # purpose: conclude planner workflows and record guardrail summary for exports
    planner = (
        db.query(models.CloningPlannerSession)
        .filter(models.CloningPlannerSession.id == session_id)
        .first()
    )
    if not planner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planner session not found")
    if planner.created_by_id not in {None, user.id} and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to planner session denied")
    finalized = cloning_planner.finalize_session(
        db,
        planner=planner,
        guardrail_state=payload.guardrail_state,
    )
    db.commit()
    db.refresh(finalized)
    return schemas.CloningPlannerSessionOut(**cloning_planner.serialize_session(finalized))
