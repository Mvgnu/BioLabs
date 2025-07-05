from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas
from ..rbac import check_team_role

router = APIRouter(prefix="/api/teams", tags=["teams"])


@router.post("/", response_model=schemas.TeamOut)
async def create_team(
    team: schemas.TeamCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    db_team = models.Team(name=team.name, created_by=user.id)
    db.add(db_team)
    db.commit()
    db.refresh(db_team)
    membership = models.TeamMember(team_id=db_team.id, user_id=user.id, role="owner")
    db.add(membership)
    db.commit()
    return db_team


@router.get("/", response_model=List[schemas.TeamOut])
async def list_teams(
    db: Session = Depends(get_db), user: models.User = Depends(get_current_user)
):
    team_ids = [m.team_id for m in user.teams]
    if not team_ids:
        return []
    return db.query(models.Team).filter(models.Team.id.in_(team_ids)).all()


@router.post("/{team_id}/members", response_model=schemas.TeamMemberOut)
async def add_member(
    team_id: str,
    member: schemas.TeamMemberAdd,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    try:
        team_uuid = UUID(team_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid team id")

    team = db.query(models.Team).filter(models.Team.id == team_uuid).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")
    check_team_role(db, user, team_uuid, ["owner"])  # only owner or admin may add members
    if member.user_id:
        db_user = db.query(models.User).filter(models.User.id == member.user_id).first()
    elif member.email:
        db_user = (
            db.query(models.User).filter(models.User.email == member.email).first()
        )
    else:
        raise HTTPException(status_code=400, detail="user_id or email required")
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    existing = (
        db.query(models.TeamMember)
        .filter(
            models.TeamMember.team_id == team_uuid,
            models.TeamMember.user_id == db_user.id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="User already member")
    membership = models.TeamMember(
        team_id=team_uuid, user_id=db_user.id, role=member.role
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    user_data = schemas.UserOut.model_validate(db_user)
    return schemas.TeamMemberOut(user=user_data, role=membership.role)
