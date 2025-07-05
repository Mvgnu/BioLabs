from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import HTTPException

from . import models


def check_team_role(db: Session, user: models.User, team_id: UUID, roles: list[str] | tuple[str, ...]):
    if user.is_admin:
        return
    membership = (
        db.query(models.TeamMember)
        .filter(models.TeamMember.team_id == team_id, models.TeamMember.user_id == user.id)
        .first()
    )
    if not membership or membership.role not in roles:
        raise HTTPException(status_code=403, detail="Not authorized")


def ensure_project_member(db: Session, user: models.User, project_id: UUID, roles: list[str] | tuple[str, ...] = ("member", "owner")):
    if user.is_admin:
        return
    membership = (
        db.query(models.ProjectMember)
        .filter(models.ProjectMember.project_id == project_id, models.ProjectMember.user_id == user.id)
        .first()
    )
    if not membership or membership.role not in roles:
        raise HTTPException(status_code=403, detail="Not authorized")


def ensure_item_access(
    db: Session,
    user: models.User,
    item_id: UUID,
    roles: list[str] | tuple[str, ...] = ("member", "manager", "owner"),
) -> models.InventoryItem:
    """Return the item if the user has access, otherwise raise 403."""
    item = db.query(models.InventoryItem).filter(models.InventoryItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if user.is_admin or item.owner_id == user.id:
        return item
    if item.team_id:
        membership = (
            db.query(models.TeamMember)
            .filter(models.TeamMember.team_id == item.team_id, models.TeamMember.user_id == user.id)
            .first()
        )
        if membership and membership.role in roles:
            return item
    raise HTTPException(status_code=403, detail="Not authorized")
