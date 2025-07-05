from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from .. import models, schemas, auth

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("/me", response_model=schemas.UserOut)
async def read_profile(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


@router.put("/me", response_model=schemas.UserOut)
async def update_profile(
    update: schemas.UserUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    if update.full_name is not None:
        current_user.full_name = update.full_name
    if update.phone_number is not None:
        current_user.phone_number = update.phone_number
    if update.orcid_id is not None:
        current_user.orcid_id = update.orcid_id
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user
