from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas
from ..rbac import check_team_role

router = APIRouter(prefix="/api/locations", tags=["locations"])

@router.post("/", response_model=schemas.LocationOut)
async def create_location(
    loc: schemas.LocationCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if loc.team_id:
        check_team_role(db, user, loc.team_id, ["owner", "manager", "member"])
    else:
        membership = user.teams[0] if user.teams else None
        if membership:
            loc.team_id = membership.team_id
    db_loc = models.Location(**loc.model_dump())
    db.add(db_loc)
    db.commit()
    db.refresh(db_loc)
    return db_loc


@router.get("/", response_model=list[schemas.LocationOut])
async def list_locations(
    team_id: UUID | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    query = db.query(models.Location)
    if team_id:
        check_team_role(db, user, team_id, ["owner", "manager", "member"])
        query = query.filter(models.Location.team_id == team_id)
    else:
        team_ids = [m.team_id for m in user.teams]
        query = query.filter(models.Location.team_id.in_(team_ids))
    return query.all()


@router.put("/{loc_id}", response_model=schemas.LocationOut)
async def update_location(
    loc_id: UUID,
    update: schemas.LocationUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    loc = db.get(models.Location, loc_id)
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    if loc.team_id:
        check_team_role(db, user, loc.team_id, ["owner", "manager"])
    for k, v in update.model_dump(exclude_unset=True).items():
        setattr(loc, k, v)
    db.commit()
    db.refresh(loc)
    return loc


@router.delete("/{loc_id}", status_code=204)
async def delete_location(
    loc_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    loc = db.get(models.Location, loc_id)
    if not loc:
        raise HTTPException(status_code=404, detail="Location not found")
    if loc.team_id:
        check_team_role(db, user, loc.team_id, ["owner", "manager"])
    db.delete(loc)
    db.commit()
    return
