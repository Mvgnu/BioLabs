"""Lifecycle narrative aggregation API routes."""

# purpose: expose lifecycle aggregation timelines across planner, custody, dna, and sharing surfaces
# status: experimental

from __future__ import annotations

from typing import Iterable
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..services import lifecycle_narrative

router = APIRouter(prefix="/api/lifecycle", tags=["lifecycle"])


@router.get("/timeline", response_model=schemas.LifecycleTimelineResponse)
def get_lifecycle_timeline(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
    planner_session_id: UUID | None = Query(default=None),
    dna_asset_id: UUID | None = Query(default=None),
    dna_asset_version_id: UUID | None = Query(default=None),
    custody_log_inventory_item_id: UUID | None = Query(default=None),
    protocol_execution_id: UUID | None = Query(default=None),
    repository_id: UUID | None = Query(default=None),
    limit: int = Query(default=250, ge=1, le=500),
) -> schemas.LifecycleTimelineResponse:
    """Aggregate lifecycle events for the provided scope."""

    scope = schemas.LifecycleScope(
        planner_session_id=planner_session_id,
        dna_asset_id=dna_asset_id,
        dna_asset_version_id=dna_asset_version_id,
        custody_log_inventory_item_id=custody_log_inventory_item_id,
        protocol_execution_id=protocol_execution_id,
        repository_id=repository_id,
    )
    if not any(scope.model_dump().values()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one scope identifier must be provided",
        )
    _assert_scope_access(db, user, scope)
    return lifecycle_narrative.build_lifecycle_timeline(db, scope, limit=limit)


def _assert_scope_access(db: Session, user: models.User, scope: schemas.LifecycleScope) -> None:
    """Ensure the user may view the requested lifecycle scope."""

    if user.is_admin:
        return
    if scope.planner_session_id:
        session = db.get(models.CloningPlannerSession, scope.planner_session_id)
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Planner session not found")
        if session.created_by_id not in {None, user.id}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to planner session denied")
    if scope.dna_asset_version_id:
        version = db.get(models.DNAAssetVersion, scope.dna_asset_version_id)
        if not version:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DNA asset version not found")
        _assert_asset_access(user, db.get(models.DNAAsset, version.asset_id))
    if scope.dna_asset_id and not scope.dna_asset_version_id:
        asset = db.get(models.DNAAsset, scope.dna_asset_id)
        if not asset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DNA asset not found")
        _assert_asset_access(user, asset)
    if scope.custody_log_inventory_item_id:
        item = db.get(models.InventoryItem, scope.custody_log_inventory_item_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory item not found")
        if item.owner_id not in {None, user.id} and item.team_id not in _user_team_ids(user):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to custody logs denied")
    if scope.protocol_execution_id:
        execution = db.get(models.ProtocolExecution, scope.protocol_execution_id)
        if not execution:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Protocol execution not found")
        if execution.created_by_id not in {None, user.id}:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to protocol execution denied")
    if scope.repository_id:
        _assert_repository_access(db, user, scope.repository_id)


def _assert_asset_access(user: models.User, asset: models.DNAAsset | None) -> None:
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="DNA asset not found")
    if asset.created_by_id not in {None, user.id}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to DNA asset denied")


def _user_team_ids(user: models.User) -> set[UUID]:
    memberships: Iterable[models.TeamMember] = user.teams or []
    return {membership.team_id for membership in memberships if membership.team_id}


def _assert_repository_access(db: Session, user: models.User, repository_id: UUID) -> None:
    repo = (
        db.query(models.DNARepository)
        .options(
            joinedload(models.DNARepository.collaborators),
        )
        .filter(models.DNARepository.id == repository_id)
        .first()
    )
    if not repo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository not found")
    if repo.owner_id == user.id:
        return
    collaborator_ids = {collaborator.user_id for collaborator in repo.collaborators}
    if user.id in collaborator_ids:
        return
    if repo.team_id and repo.team_id in _user_team_ids(user):
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to repository denied")

