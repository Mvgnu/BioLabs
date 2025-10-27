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


def _record_template_audit(
    db: Session,
    *,
    template_id: UUID,
    actor_id: UUID,
    action: str,
    snapshot_id: UUID | None = None,
    detail: dict | None = None,
) -> None:
    """Persist governance lifecycle audit events."""

    # purpose: centralize governance lifecycle telemetry persistence
    # inputs: database session, lifecycle metadata, acting user and snapshot identifiers
    # outputs: GovernanceTemplateAuditLog row capturing lifecycle action context
    # status: pilot
    entry = models.GovernanceTemplateAuditLog(
        template_id=template_id,
        snapshot_id=snapshot_id,
        actor_id=actor_id,
        action=action,
        detail=detail or {},
    )
    db.add(entry)


def _create_template_snapshot(
    db: Session,
    *,
    template: models.ExecutionNarrativeWorkflowTemplate,
    actor_id: UUID,
) -> models.ExecutionNarrativeWorkflowTemplateSnapshot:
    """Persist the current template payload as an immutable snapshot."""

    # purpose: bind governance templates to immutable payloads for export enforcement
    # inputs: template ORM entity, acting user identifier
    # outputs: stored snapshot instance for downstream export binding
    # status: pilot
    payload = {
        "template_id": str(template.id),
        "template_key": template.template_key,
        "version": template.version,
        "name": template.name,
        "description": template.description,
        "default_stage_sla_hours": template.default_stage_sla_hours,
        "permitted_roles": template.permitted_roles or [],
        "stage_blueprint": template.stage_blueprint or [],
        "status": template.status,
        "captured_at": datetime.now(timezone.utc).isoformat(),
    }
    snapshot = models.ExecutionNarrativeWorkflowTemplateSnapshot(
        template_id=template.id,
        template_key=template.template_key,
        version=template.version,
        status=template.status,
        captured_by_id=actor_id,
    )
    snapshot.snapshot_payload = payload
    db.add(snapshot)
    db.flush()
    _record_template_audit(
        db,
        template_id=template.id,
        actor_id=actor_id,
        action="template.snapshot.created",
        snapshot_id=snapshot.id,
        detail={"version": template.version, "status": template.status},
    )
    return snapshot


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
        query = query.filter(
            models.ExecutionNarrativeWorkflowTemplate.is_latest.is_(True),
            models.ExecutionNarrativeWorkflowTemplate.status != "archived",
        )
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
    db.flush()
    _record_template_audit(
        db,
        template_id=template.id,
        actor_id=user.id,
        action="template.created",
        detail={"version": version, "status": status_value},
    )
    if template.status == "published":
        snapshot = _create_template_snapshot(db, template=template, actor_id=user.id)
        template.published_snapshot_id = snapshot.id
        template.published_at = template.published_at or now
    db.commit()
    db.refresh(template)
    return template


@router.post(
    "/templates/{template_id}/publish",
    response_model=schemas.ExecutionNarrativeWorkflowTemplateOut,
)
def publish_workflow_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Transition a governance template into the published state."""

    _require_admin(user)
    template = db.get(models.ExecutionNarrativeWorkflowTemplate, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    if template.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Archived templates cannot be republished",
        )
    if template.status == "published":
        return template
    snapshot = _create_template_snapshot(db, template=template, actor_id=user.id)
    template.status = "published"
    template.published_at = datetime.now(timezone.utc)
    template.updated_at = template.published_at
    template.published_snapshot_id = snapshot.id
    template.is_latest = True
    _record_template_audit(
        db,
        template_id=template.id,
        actor_id=user.id,
        action="template.published",
        snapshot_id=snapshot.id,
        detail={"version": template.version},
    )
    db.commit()
    db.refresh(template)
    return template


@router.post(
    "/templates/{template_id}/archive",
    response_model=schemas.ExecutionNarrativeWorkflowTemplateOut,
)
def archive_workflow_template(
    template_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Archive a governance template and exclude it from active listings."""

    _require_admin(user)
    template = db.get(models.ExecutionNarrativeWorkflowTemplate, template_id)
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    if template.status == "archived":
        return template
    template.status = "archived"
    template.updated_at = datetime.now(timezone.utc)
    template.is_latest = False
    _record_template_audit(
        db,
        template_id=template.id,
        actor_id=user.id,
        action="template.archived",
        detail={"version": template.version},
    )
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
    if template.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot assign archived templates",
        )
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
