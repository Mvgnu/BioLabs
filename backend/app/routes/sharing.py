from __future__ import annotations

from typing import List
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..services import sharing_workspace

# purpose: expose guarded DNA sharing workspace APIs with guardrail enforcement
# status: experimental

router = APIRouter(prefix="/api/sharing", tags=["sharing"])


@router.get("/repositories", response_model=List[schemas.DNARepositoryOut])
def list_repositories(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> List[models.DNARepository]:
    team_ids = [
        membership.team_id
        for membership in user.teams
        if membership.team_id is not None
    ]
    query = (
        db.query(models.DNARepository)
        .options(
            joinedload(models.DNARepository.collaborators),
            joinedload(models.DNARepository.releases).joinedload(models.DNARepositoryRelease.approvals),
        )
        .filter(
            sa.or_(
                models.DNARepository.owner_id == user.id,
                models.DNARepository.collaborators.any(
                    models.DNARepositoryCollaborator.user_id == user.id
                ),
                models.DNARepository.team_id.in_(team_ids) if team_ids else sa.false(),
            )
        )
        .order_by(models.DNARepository.updated_at.desc())
    )
    repositories = query.all()
    return repositories


@router.post("/repositories", response_model=schemas.DNARepositoryOut, status_code=status.HTTP_201_CREATED)
def create_repository(
    payload: schemas.DNARepositoryCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.DNARepository:
    existing = (
        db.query(models.DNARepository)
        .filter(sa.func.lower(models.DNARepository.slug) == payload.slug.lower())
        .one_or_none()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Repository slug already in use")
    repo = sharing_workspace.create_repository(db, payload, owner_id=user.id)
    db.commit()
    db.refresh(repo)
    return repo


@router.patch("/repositories/{repository_id}", response_model=schemas.DNARepositoryOut)
def update_repository(
    repository_id: UUID,
    payload: schemas.DNARepositoryUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.DNARepository:
    repo = db.get(models.DNARepository, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Only owners can update repositories")
    repo = sharing_workspace.update_repository(db, repo, payload, actor_id=user.id)
    db.commit()
    db.refresh(repo)
    return repo


@router.post("/repositories/{repository_id}/collaborators", response_model=schemas.DNARepositoryCollaboratorOut, status_code=status.HTTP_201_CREATED)
def add_collaborator(
    repository_id: UUID,
    payload: schemas.DNARepositoryCollaboratorAdd,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.DNARepositoryCollaborator:
    repo = db.get(models.DNARepository, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo.owner_id != user.id and user.id != payload.user_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions to invite collaborators")
    try:
        collaborator = sharing_workspace.add_collaborator(
            db,
            repo,
            user_id=payload.user_id,
            role=payload.role,
            actor_id=user.id,
        )
        db.commit()
    except IntegrityError as exc:  # pragma: no cover - defensive
        db.rollback()
        raise HTTPException(status_code=400, detail="Collaborator already invited") from exc
    db.refresh(collaborator)
    return collaborator


@router.post(
    "/repositories/{repository_id}/releases",
    response_model=schemas.DNARepositoryReleaseOut,
    status_code=status.HTTP_201_CREATED,
)
def create_release(
    repository_id: UUID,
    payload: schemas.DNARepositoryReleaseCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.DNARepositoryRelease:
    repo = (
        db.query(models.DNARepository)
        .options(joinedload(models.DNARepository.collaborators))
        .filter(models.DNARepository.id == repository_id)
        .one_or_none()
    )
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if not _user_can_publish(user, repo):
        raise HTTPException(status_code=403, detail="Insufficient permissions to create releases")
    try:
        release = sharing_workspace.create_release(db, repo, payload, actor_id=user.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Release version already exists") from exc
    db.refresh(release)
    db.refresh(repo)
    return release


@router.post(
    "/releases/{release_id}/approvals",
    response_model=schemas.DNARepositoryReleaseOut,
)
def approve_release(
    release_id: UUID,
    payload: schemas.DNARepositoryReleaseApprovalCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.DNARepositoryRelease:
    release = (
        db.query(models.DNARepositoryRelease)
        .options(joinedload(models.DNARepositoryRelease.repository).joinedload(models.DNARepository.collaborators))
        .filter(models.DNARepositoryRelease.id == release_id)
        .one_or_none()
    )
    if not release:
        raise HTTPException(status_code=404, detail="Release not found")
    if not _user_can_approve(user, release.repository):
        raise HTTPException(status_code=403, detail="Insufficient permissions to approve releases")
    release = sharing_workspace.record_release_approval(
        db,
        release,
        approver_id=user.id,
        approval_payload=payload,
    )
    db.commit()
    db.refresh(release)
    return release


@router.get(
    "/repositories/{repository_id}/timeline",
    response_model=List[schemas.DNARepositoryTimelineEventOut],
)
def get_timeline(
    repository_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> List[models.DNARepositoryTimelineEvent]:
    repo = db.get(models.DNARepository, repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    if not _user_can_view(user, repo):
        raise HTTPException(status_code=403, detail="Insufficient permissions to view timeline")
    events = (
        db.query(models.DNARepositoryTimelineEvent)
        .filter(models.DNARepositoryTimelineEvent.repository_id == repository_id)
        .order_by(models.DNARepositoryTimelineEvent.created_at.desc())
        .all()
    )
    return events


def _user_can_view(user: models.User, repo: models.DNARepository) -> bool:
    if repo.owner_id == user.id:
        return True
    if any(collab.user_id == user.id for collab in repo.collaborators):
        return True
    return bool(
        repo.team_id
        and any(team.team_id == repo.team_id for team in user.teams)
    )


def _user_can_publish(user: models.User, repo: models.DNARepository) -> bool:
    if repo.owner_id == user.id:
        return True
    return any(
        collab.user_id == user.id and collab.role in {"maintainer", "owner"}
        for collab in repo.collaborators
    )


def _user_can_approve(user: models.User, repo: models.DNARepository) -> bool:
    if repo.owner_id == user.id:
        return True
    return any(
        collab.user_id == user.id and collab.role in {"maintainer", "owner"}
        for collab in repo.collaborators
    )
