from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/api/governance", tags=["governance"])


def _require_admin(user: models.User) -> None:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required")


@router.get(
    "/templates",
    response_model=list[schemas.ExecutionNarrativeWorkflowTemplateOut],
)
def list_workflow_templates(
    include_all: bool = False,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _require_admin(user)
    query = db.query(models.ExecutionNarrativeWorkflowTemplate)
    if not include_all:
        query = query.filter(models.ExecutionNarrativeWorkflowTemplate.is_latest.is_(True))
    templates = (
        query.order_by(
            models.ExecutionNarrativeWorkflowTemplate.template_key.asc(),
            models.ExecutionNarrativeWorkflowTemplate.version.desc(),
        )
        .all()
    )
    return templates


@router.get(
    "/templates/{template_id}",
    response_model=schemas.ExecutionNarrativeWorkflowTemplateOut,
)
def get_workflow_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _require_admin(user)
    template = db.get(models.ExecutionNarrativeWorkflowTemplate, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    return template


def _resolve_template_version(
    db: Session,
    template_in: schemas.ExecutionNarrativeWorkflowTemplateCreate,
) -> tuple[str, int, UUID | None]:
    """Determine template key, new version number, and lineage reference."""

    template_key = template_in.template_key
    forked_from_id = template_in.forked_from_id
    parent: models.ExecutionNarrativeWorkflowTemplate | None = None
    if forked_from_id:
        parent = db.get(models.ExecutionNarrativeWorkflowTemplate, forked_from_id)
        if not parent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent template not found")
        template_key = parent.template_key
    latest = (
        db.query(models.ExecutionNarrativeWorkflowTemplate)
        .filter(models.ExecutionNarrativeWorkflowTemplate.template_key == template_key)
        .order_by(models.ExecutionNarrativeWorkflowTemplate.version.desc())
        .first()
    )
    if latest:
        if latest.is_latest:
            latest.is_latest = False
            latest.updated_at = datetime.now(timezone.utc)
        if forked_from_id is None:
            forked_from_id = latest.id
        version = latest.version + 1
    else:
        version = 1
    return template_key, version, forked_from_id


@router.post(
    "/templates",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.ExecutionNarrativeWorkflowTemplateOut,
)
def create_workflow_template(
    template_in: schemas.ExecutionNarrativeWorkflowTemplateCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _require_admin(user)
    template_key, version, forked_from_id = _resolve_template_version(db, template_in)
    now = datetime.now(timezone.utc)
    stage_blueprint = [
        stage.model_dump(exclude_none=True) for stage in template_in.stage_blueprint
    ]
    status_value = "published" if template_in.publish else "draft"
    template = models.ExecutionNarrativeWorkflowTemplate(
        template_key=template_key,
        name=template_in.name,
        description=template_in.description,
        version=version,
        stage_blueprint=stage_blueprint,
        default_stage_sla_hours=template_in.default_stage_sla_hours,
        permitted_roles=template_in.permitted_roles or [],
        status=status_value,
        forked_from_id=forked_from_id,
        created_by_id=user.id,
        created_at=now,
        updated_at=now,
        published_at=now if template_in.publish else None,
        is_latest=True,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.get(
    "/templates/{template_id}/assignments",
    response_model=list[schemas.ExecutionNarrativeWorkflowTemplateAssignmentOut],
)
def list_template_assignments(
    template_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _require_admin(user)
    template = db.get(models.ExecutionNarrativeWorkflowTemplate, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    assignments = (
        db.query(models.ExecutionNarrativeWorkflowTemplateAssignment)
        .filter(models.ExecutionNarrativeWorkflowTemplateAssignment.template_id == template_id)
        .order_by(models.ExecutionNarrativeWorkflowTemplateAssignment.created_at.asc())
        .all()
    )
    return assignments


@router.post(
    "/templates/{template_id}/assignments",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.ExecutionNarrativeWorkflowTemplateAssignmentOut,
)
def create_template_assignment(
    template_id: UUID,
    assignment_in: schemas.ExecutionNarrativeWorkflowTemplateAssignmentCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _require_admin(user)
    template = db.get(models.ExecutionNarrativeWorkflowTemplate, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    if not assignment_in.team_id and not assignment_in.protocol_template_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assignment requires a team_id or protocol_template_id",
        )
    assignment = models.ExecutionNarrativeWorkflowTemplateAssignment(
        template_id=template.id,
        team_id=assignment_in.team_id,
        protocol_template_id=assignment_in.protocol_template_id,
        created_by_id=user.id,
        created_at=datetime.now(timezone.utc),
    )
    assignment.meta = assignment_in.metadata or {}
    db.add(assignment)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assignment already exists for target",
        ) from exc
    db.refresh(assignment)
    return assignment


@router.delete(
    "/assignments/{assignment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_template_assignment(
    assignment_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _require_admin(user)
    assignment = db.get(models.ExecutionNarrativeWorkflowTemplateAssignment, assignment_id)
    if not assignment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assignment not found")
    db.delete(assignment)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
