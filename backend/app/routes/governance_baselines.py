from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..eventlog import record_baseline_event
from .experiment_console import _ensure_execution_access, _get_user_team_ids

router = APIRouter(prefix="/api/governance/baselines", tags=["governance-baselines"])


def _serialize_labels(labels: Iterable[schemas.BaselineLifecycleLabel] | None) -> list[dict[str, str]]:
    """Normalize label payloads for persistence."""

    # purpose: convert baseline label schemas into JSON serialisable dicts
    # inputs: iterable of BaselineLifecycleLabel
    # outputs: list of string-keyed dictionaries
    # status: draft
    sanitized: list[dict[str, str]] = []
    if not labels:
        return sanitized
    for label in labels:
        if not getattr(label, "key", None):
            continue
        value = getattr(label, "value", "")
        sanitized.append({"key": str(label.key), "value": str(value)})
    return sanitized


def _reviewer_set(baseline: models.GovernanceBaselineVersion) -> set[str]:
    """Return reviewer identifiers attached to a baseline."""

    # purpose: provide consistent reviewer comparison for RBAC enforcement
    # inputs: baseline reviewer JSON payload
    # outputs: set of stringified reviewer UUIDs
    # status: draft
    if not isinstance(baseline.reviewer_ids, list):
        return set()
    return {str(entry) for entry in baseline.reviewer_ids if entry}


def _assert_reviewer_access(
    baseline: models.GovernanceBaselineVersion,
    user: models.User,
) -> None:
    """Ensure caller can perform reviewer-level transitions."""

    # purpose: guard review and publish flows behind reviewer/admin RBAC
    # inputs: baseline instance and authenticated user
    # outputs: raises HTTPException on violation
    # status: draft
    if user.is_admin:
        return
    if str(user.id) in _reviewer_set(baseline):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Reviewer access required")


def _assert_baseline_visibility(
    db: Session,
    baseline: models.GovernanceBaselineVersion,
    user: models.User,
    team_ids: set[UUID],
) -> None:
    """Check whether the authenticated user can view the baseline."""

    # purpose: enforce least-privilege access to baseline catalogue entries
    # inputs: baseline entity, authenticated user, cached team identifiers
    # outputs: raises HTTPException when unauthorized
    # status: draft
    if user.is_admin:
        return
    if baseline.submitted_by_id == user.id:
        return
    if str(user.id) in _reviewer_set(baseline):
        return
    if baseline.team_id and baseline.team_id in team_ids:
        return
    execution = db.get(models.ProtocolExecution, baseline.execution_id)
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    _ensure_execution_access(db, execution, user, team_ids)


def _load_baseline(db: Session, baseline_id: UUID) -> models.GovernanceBaselineVersion | None:
    """Load a baseline with events eager loaded."""

    # purpose: centralize baseline eager loading for response payloads
    # inputs: database session and baseline identifier
    # outputs: GovernanceBaselineVersion with events relationship populated
    # status: draft
    stmt = (
        select(models.GovernanceBaselineVersion)
        .options(joinedload(models.GovernanceBaselineVersion.events))
        .where(models.GovernanceBaselineVersion.id == baseline_id)
    )
    result = db.execute(stmt).unique().scalars().first()
    return result


@router.post(
    "/submissions",
    response_model=schemas.GovernanceBaselineVersionOut,
    status_code=status.HTTP_201_CREATED,
)
def submit_baseline(
    payload: schemas.BaselineSubmissionRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.GovernanceBaselineVersionOut:
    """Create a baseline submission anchored to a governance execution."""

    team_ids = _get_user_team_ids(db, user)
    execution = db.get(models.ProtocolExecution, payload.execution_id)
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    template = _ensure_execution_access(db, execution, user, team_ids)

    baseline = models.GovernanceBaselineVersion(
        execution_id=execution.id,
        template_id=getattr(template, "id", None),
        team_id=getattr(template, "team_id", None),
        name=payload.name,
        description=payload.description,
        status="submitted",
        labels=_serialize_labels(payload.labels),
        reviewer_ids=[str(identifier) for identifier in payload.reviewer_ids],
        submitted_by_id=user.id,
        submitted_at=datetime.now(timezone.utc),
    )
    db.add(baseline)
    db.flush()

    record_baseline_event(
        db,
        baseline,
        action="submitted",
        detail={"execution_id": str(execution.id)},
        actor=user,
        notes=payload.description,
    )
    db.commit()

    refreshed = _load_baseline(db, baseline.id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baseline not found")
    return refreshed


@router.get("", response_model=schemas.GovernanceBaselineCollection)
def list_baselines(
    execution_id: UUID | None = Query(None),
    template_id: UUID | None = Query(None),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.GovernanceBaselineCollection:
    """Enumerate accessible baselines for the authenticated user."""

    team_ids = _get_user_team_ids(db, user)
    query = (
        select(models.GovernanceBaselineVersion)
        .options(joinedload(models.GovernanceBaselineVersion.events))
        .order_by(models.GovernanceBaselineVersion.created_at.desc())
    )

    if execution_id is not None:
        execution = db.get(models.ProtocolExecution, execution_id)
        if execution is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
        _ensure_execution_access(db, execution, user, team_ids)
        query = query.where(models.GovernanceBaselineVersion.execution_id == execution_id)

    if template_id is not None:
        query = query.where(models.GovernanceBaselineVersion.template_id == template_id)

    baselines = db.execute(query).unique().scalars().all()
    accessible: list[models.GovernanceBaselineVersion] = []
    for baseline in baselines:
        try:
            _assert_baseline_visibility(db, baseline, user, team_ids)
        except HTTPException as exc:
            if exc.status_code == status.HTTP_403_FORBIDDEN:
                continue
            raise
        accessible.append(baseline)
    return schemas.GovernanceBaselineCollection(items=accessible)


@router.get("/{baseline_id}", response_model=schemas.GovernanceBaselineVersionOut)
def get_baseline(
    baseline_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.GovernanceBaselineVersionOut:
    """Return a single baseline with lifecycle history."""

    team_ids = _get_user_team_ids(db, user)
    baseline = _load_baseline(db, baseline_id)
    if baseline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baseline not found")
    _assert_baseline_visibility(db, baseline, user, team_ids)
    return baseline


@router.post("/{baseline_id}/review", response_model=schemas.GovernanceBaselineVersionOut)
def review_baseline(
    baseline_id: UUID,
    payload: schemas.BaselineReviewRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.GovernanceBaselineVersionOut:
    """Approve or reject a submitted baseline."""

    baseline = _load_baseline(db, baseline_id)
    if baseline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baseline not found")
    team_ids = _get_user_team_ids(db, user)
    _assert_baseline_visibility(db, baseline, user, team_ids)
    _assert_reviewer_access(baseline, user)

    if baseline.status not in {"submitted", "rejected"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Baseline not awaiting review")

    decision = payload.decision
    now = datetime.now(timezone.utc)
    baseline.reviewed_by_id = user.id
    baseline.reviewed_at = now
    baseline.review_notes = payload.notes
    baseline.status = "approved" if decision == "approve" else "rejected"

    record_baseline_event(
        db,
        baseline,
        action=f"review.{decision}",
        detail={"decision": decision},
        actor=user,
        notes=payload.notes,
    )
    db.commit()

    refreshed = _load_baseline(db, baseline.id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baseline not found")
    return refreshed


@router.post("/{baseline_id}/publish", response_model=schemas.GovernanceBaselineVersionOut)
def publish_baseline(
    baseline_id: UUID,
    payload: schemas.BaselinePublishRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.GovernanceBaselineVersionOut:
    """Publish an approved baseline and retire previous versions."""

    baseline = _load_baseline(db, baseline_id)
    if baseline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baseline not found")
    team_ids = _get_user_team_ids(db, user)
    _assert_baseline_visibility(db, baseline, user, team_ids)
    _assert_reviewer_access(baseline, user)

    if baseline.status != "approved":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Baseline must be approved before publishing")

    now = datetime.now(timezone.utc)
    baseline.published_by_id = user.id
    baseline.published_at = now
    baseline.publish_notes = payload.notes
    baseline.status = "published"
    baseline.is_current = True

    if baseline.version_number is None and baseline.template_id is not None:
        prior_count = (
            db.query(models.GovernanceBaselineVersion)
            .filter(
                models.GovernanceBaselineVersion.template_id == baseline.template_id,
                models.GovernanceBaselineVersion.status == "published",
                models.GovernanceBaselineVersion.id != baseline.id,
            )
            .count()
        )
        baseline.version_number = prior_count + 1

    if baseline.template_id is not None:
        (
            db.query(models.GovernanceBaselineVersion)
            .filter(
                models.GovernanceBaselineVersion.template_id == baseline.template_id,
                models.GovernanceBaselineVersion.id != baseline.id,
            )
            .update({"is_current": False}, synchronize_session=False)
        )

    record_baseline_event(
        db,
        baseline,
        action="published",
        detail={
            "version_number": baseline.version_number,
            "template_id": str(baseline.template_id) if baseline.template_id else None,
        },
        actor=user,
        notes=payload.notes,
    )
    db.commit()

    refreshed = _load_baseline(db, baseline.id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baseline not found")
    return refreshed


@router.post("/{baseline_id}/rollback", response_model=schemas.GovernanceBaselineVersionOut)
def rollback_baseline(
    baseline_id: UUID,
    payload: schemas.BaselineRollbackRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.GovernanceBaselineVersionOut:
    """Rollback a published baseline and optionally reinstate an earlier version."""

    baseline = _load_baseline(db, baseline_id)
    if baseline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baseline not found")
    team_ids = _get_user_team_ids(db, user)
    _assert_baseline_visibility(db, baseline, user, team_ids)
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required for rollback")

    if baseline.status != "published":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only published baselines can be rolled back")

    now = datetime.now(timezone.utc)
    baseline.status = "rolled_back"
    baseline.is_current = False
    baseline.rolled_back_by_id = user.id
    baseline.rolled_back_at = now
    baseline.rollback_notes = payload.reason
    baseline.rollback_of_id = payload.target_version_id

    restored: models.GovernanceBaselineVersion | None = None
    if payload.target_version_id:
        restored = _load_baseline(db, payload.target_version_id)
        if restored is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target baseline not found")
        restored.status = "published"
        restored.is_current = True
        restored.rolled_back_at = None
        restored.rolled_back_by_id = None
        restored.rollback_notes = None

    record_baseline_event(
        db,
        baseline,
        action="rolled_back",
        detail={
            "reason": payload.reason,
            "target_version_id": str(payload.target_version_id) if payload.target_version_id else None,
        },
        actor=user,
        notes=payload.reason,
    )
    if restored is not None:
        record_baseline_event(
            db,
            restored,
            action="restored",
            detail={"rolled_back_from": str(baseline.id)},
            actor=user,
            notes=payload.reason,
        )

    db.commit()

    refreshed = _load_baseline(db, baseline.id)
    if refreshed is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baseline not found")
    return refreshed
