from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..recommendations.governance import generate_override_recommendations
from ..recommendations import actions as recommendation_actions
from .experiment_console import _ensure_execution_access, _get_user_team_ids
from .governance_baselines import _assert_baseline_visibility, _load_baseline

router = APIRouter(
    prefix="/api/governance/recommendations",
    tags=["governance-recommendations"],
)

# purpose: expose governance override recommendations scoped by RBAC and execution access
# inputs: optional execution identifier, pagination limit, authenticated user context
# outputs: GovernanceOverrideRecommendationReport payload with staffing advisories
# status: pilot


@router.get(
    "/override",
    response_model=schemas.GovernanceOverrideRecommendationReport,
)
def read_governance_override_recommendations(
    execution_id: UUID | None = Query(default=None),
    limit: int | None = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.GovernanceOverrideRecommendationReport:
    """Return override recommendations for governance operators."""

    team_ids = _get_user_team_ids(db, user)

    execution_ids: list[UUID] | None = None
    if execution_id:
        execution = db.get(models.ProtocolExecution, execution_id)
        if execution is None:
            raise HTTPException(status_code=404, detail="Execution not found")
        _ensure_execution_access(db, execution, user, team_ids)
        execution_ids = [execution_id]

    report = generate_override_recommendations(
        db,
        user,
        team_ids=team_ids,
        execution_ids=execution_ids,
        limit=limit,
    )

    db.flush()
    return report



def _prepare_override_context(
    db: Session,
    user: models.User,
    payload: schemas.GovernanceOverrideActionRequest,
) -> tuple[
    models.ProtocolExecution,
    models.GovernanceBaselineVersion | None,
    models.User | None,
]:
    team_ids = _get_user_team_ids(db, user)
    execution = db.get(models.ProtocolExecution, payload.execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    _ensure_execution_access(db, execution, user, team_ids)

    baseline: models.GovernanceBaselineVersion | None = None
    if payload.baseline_id is not None:
        baseline = _load_baseline(db, payload.baseline_id)
        if baseline is None:
            raise HTTPException(status_code=404, detail="Baseline not found")
        if baseline.execution_id != execution.id:
            raise HTTPException(status_code=400, detail="Baseline does not belong to execution")
        _assert_baseline_visibility(db, baseline, user, team_ids)

    target: models.User | None = None
    if payload.target_reviewer_id is not None:
        target = db.get(models.User, payload.target_reviewer_id)
        if target is None:
            raise HTTPException(status_code=404, detail="Target reviewer not found")

    return execution, baseline, target


def _prepare_reverse_context(
    db: Session,
    user: models.User,
    payload: schemas.GovernanceOverrideReverseRequest,
) -> tuple[
    models.ProtocolExecution,
    models.GovernanceBaselineVersion | None,
]:
    team_ids = _get_user_team_ids(db, user)
    execution = db.get(models.ProtocolExecution, payload.execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    _ensure_execution_access(db, execution, user, team_ids)

    baseline: models.GovernanceBaselineVersion | None = None
    if payload.baseline_id is not None:
        baseline = _load_baseline(db, payload.baseline_id)
        if baseline is None:
            raise HTTPException(status_code=404, detail="Baseline not found")
        if baseline.execution_id != execution.id:
            raise HTTPException(status_code=400, detail="Baseline does not belong to execution")
        _assert_baseline_visibility(db, baseline, user, team_ids)

    return execution, baseline


@router.post(
    "/override/{recommendation_id}/accept",
    response_model=schemas.GovernanceOverrideActionOutcome,
)
def accept_governance_override(
    recommendation_id: str,
    payload: schemas.GovernanceOverrideActionRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.GovernanceOverrideActionOutcome:
    """Accept an override recommendation and persist pending action state."""

    try:
        execution, baseline, _ = _prepare_override_context(db, user, payload)
        if payload.lineage is None:
            raise HTTPException(
                status_code=422,
                detail="Override lineage payload is required for governance actions",
            )
        record, _ = recommendation_actions.accept_override(
            db,
            actor=user,
            recommendation_id=recommendation_id,
            action=payload.action,
            execution=execution,
            baseline=baseline,
            target_reviewer_id=payload.target_reviewer_id,
            notes=payload.notes,
            metadata=payload.metadata,
            lineage=payload.lineage,
        )
        db.commit()
        db.refresh(record)
        return record
    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/override/{recommendation_id}/reverse",
    response_model=schemas.GovernanceOverrideActionOutcome,
)
def reverse_governance_override(
    recommendation_id: str,
    payload: schemas.GovernanceOverrideReverseRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.GovernanceOverrideActionOutcome:
    """Reverse a previously executed override when reversible."""

    try:
        execution, baseline = _prepare_reverse_context(db, user, payload)
        record, _ = recommendation_actions.reverse_override(
            db,
            actor=user,
            recommendation_id=recommendation_id,
            execution=execution,
            baseline=baseline,
            notes=payload.notes,
            metadata=payload.metadata,
        )
        db.commit()
        db.refresh(record)
        return record
    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/override/{recommendation_id}/decline",
    response_model=schemas.GovernanceOverrideActionOutcome,
)
def decline_governance_override(
    recommendation_id: str,
    payload: schemas.GovernanceOverrideActionRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.GovernanceOverrideActionOutcome:
    """Decline an override recommendation and log lineage."""

    try:
        execution, baseline, _ = _prepare_override_context(db, user, payload)
        if payload.lineage is None:
            raise HTTPException(
                status_code=422,
                detail="Override lineage payload is required for governance actions",
            )
        record, _ = recommendation_actions.decline_override(
            db,
            actor=user,
            recommendation_id=recommendation_id,
            action=payload.action,
            execution=execution,
            baseline=baseline,
            notes=payload.notes,
            metadata=payload.metadata,
            lineage=payload.lineage,
        )
        db.commit()
        db.refresh(record)
        return record
    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/override/{recommendation_id}/execute",
    response_model=schemas.GovernanceOverrideActionOutcome,
)
def execute_governance_override(
    recommendation_id: str,
    payload: schemas.GovernanceOverrideActionRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.GovernanceOverrideActionOutcome:
    """Execute an override recommendation and apply staffing adjustments."""

    try:
        execution, baseline, target = _prepare_override_context(db, user, payload)
        if payload.lineage is None:
            raise HTTPException(
                status_code=422,
                detail="Override lineage payload is required for governance actions",
            )
        record, _ = recommendation_actions.execute_override(
            db,
            actor=user,
            recommendation_id=recommendation_id,
            action=payload.action,
            execution=execution,
            baseline=baseline,
            target_reviewer_id=getattr(target, "id", None),
            notes=payload.notes,
            metadata=payload.metadata,
            lineage=payload.lineage,
        )
        db.commit()
        db.refresh(record)
        return record
    except HTTPException:
        db.rollback()
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc))

