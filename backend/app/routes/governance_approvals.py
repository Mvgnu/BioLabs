"""Governance-facing APIs for staged narrative approval ladders."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..services import approval_ladders
from ..workers.packaging import enqueue_narrative_export_packaging

router = APIRouter(prefix="/api/governance/exports", tags=["governance"])

# purpose: expose governance approval ladder controls for operators
# status: pilot
# depends_on: services.approval_ladders, workers.packaging


def _require_admin(user: models.User) -> None:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")


@router.get("/{export_id}", response_model=schemas.ExecutionNarrativeExport)
def get_execution_export_ladder(
    export_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.ExecutionNarrativeExport:
    """Return the approval ladder state for a narrative export."""

    _require_admin(user)
    try:
        export_uuid = UUID(export_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid export identifier") from exc

    export_record = approval_ladders.load_export_with_ladder(
        db,
        export_id=export_uuid,
        include_attachments=True,
        include_guardrails=True,
    )
    approval_ladders.attach_guardrail_history(db, export_record)
    return schemas.ExecutionNarrativeExport.model_validate(export_record)


@router.post("/{export_id}/approve", response_model=schemas.ExecutionNarrativeExport)
def admin_approve_execution_export(
    export_id: str,
    approval: schemas.ExecutionNarrativeApprovalRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.ExecutionNarrativeExport:
    """Approve or reject an export stage from the governance workspace."""

    _require_admin(user)
    try:
        export_uuid = UUID(export_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid export identifier") from exc

    export_record = approval_ladders.load_export_with_ladder(
        db,
        export_id=export_uuid,
        include_attachments=True,
        include_guardrails=True,
    )
    result = approval_ladders.record_stage_decision(
        db,
        export=export_record,
        approval=approval,
        acting_user=user,
    )
    db.commit()
    db.refresh(export_record)

    if result.should_queue_packaging:
        dispatch_ready = approval_ladders.record_packaging_queue_state(
            db,
            export=export_record,
            actor=user,
        )
        db.commit()
        if dispatch_ready:
            enqueue_narrative_export_packaging(export_record.id)
        db.refresh(export_record)

    approval_ladders.attach_guardrail_forecast(db, export_record)
    approval_ladders.attach_guardrail_history(db, export_record)
    return schemas.ExecutionNarrativeExport.model_validate(export_record)


@router.post(
    "/{export_id}/stages/{stage_id}/delegate",
    response_model=schemas.ExecutionNarrativeExport,
)
def admin_delegate_export_stage(
    export_id: str,
    stage_id: str,
    request: schemas.ExecutionNarrativeApprovalDelegationRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.ExecutionNarrativeExport:
    """Delegate an approval stage to another reviewer."""

    _require_admin(user)
    try:
        export_uuid = UUID(export_id)
        stage_uuid = UUID(stage_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid identifier supplied") from exc

    export_record = approval_ladders.load_export_with_ladder(
        db,
        export_id=export_uuid,
        include_attachments=True,
        include_guardrails=True,
    )
    export_record = approval_ladders.delegate_stage(
        db,
        export=export_record,
        stage_id=stage_uuid,
        payload=request,
        acting_user=user,
    )
    db.commit()
    db.refresh(export_record)
    approval_ladders.attach_guardrail_forecast(db, export_record)
    approval_ladders.attach_guardrail_history(db, export_record)
    return schemas.ExecutionNarrativeExport.model_validate(export_record)


@router.post(
    "/{export_id}/stages/{stage_id}/reset",
    response_model=schemas.ExecutionNarrativeExport,
)
def admin_reset_export_stage(
    export_id: str,
    stage_id: str,
    request: schemas.ExecutionNarrativeApprovalResetRequest,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.ExecutionNarrativeExport:
    """Reset a stage back to in-progress for remediation."""

    _require_admin(user)
    try:
        export_uuid = UUID(export_id)
        stage_uuid = UUID(stage_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid identifier supplied") from exc

    export_record = approval_ladders.load_export_with_ladder(
        db,
        export_id=export_uuid,
        include_attachments=True,
        include_guardrails=True,
    )
    export_record = approval_ladders.reset_stage(
        db,
        export=export_record,
        stage_id=stage_uuid,
        payload=request,
        acting_user=user,
    )
    db.commit()
    db.refresh(export_record)
    approval_ladders.attach_guardrail_forecast(db, export_record)
    approval_ladders.attach_guardrail_history(db, export_record)
    return schemas.ExecutionNarrativeExport.model_validate(export_record)
