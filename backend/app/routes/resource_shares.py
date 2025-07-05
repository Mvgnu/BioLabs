from typing import List
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas

router = APIRouter(prefix="/api/resource-shares", tags=["resource_shares"])

@router.post("", response_model=schemas.ResourceShareOut)
def request_share(
    data: schemas.ResourceShareCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    lab = db.query(models.Lab).filter_by(owner_id=user.id).first()
    if not lab:
        raise HTTPException(status_code=400, detail="No lab owned by user")
    share = models.ResourceShare(
        resource_id=data.resource_id,
        from_lab=lab.id,
        to_lab=data.to_lab,
        start_date=data.start_date,
        end_date=data.end_date,
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return share

@router.get("", response_model=List[schemas.ResourceShareOut])
def list_shares(db: Session = Depends(get_db), user = Depends(get_current_user)):
    labs = db.query(models.Lab).filter(models.Lab.owner_id == user.id).all()
    lab_ids = [l.id for l in labs]
    if not lab_ids:
        return []
    return (
        db.query(models.ResourceShare)
        .filter(models.ResourceShare.from_lab.in_(lab_ids) | models.ResourceShare.to_lab.in_(lab_ids))
        .all()
    )

@router.post("/{share_id}/accept", response_model=schemas.ResourceShareOut)
def accept_share(share_id: UUID, db: Session = Depends(get_db), user = Depends(get_current_user)):
    share = db.get(models.ResourceShare, share_id)
    if not share:
        raise HTTPException(status_code=404)
    lab = db.get(models.Lab, share.to_lab)
    if not lab or lab.owner_id != user.id:
        raise HTTPException(status_code=403)
    share.status = "accepted"
    db.commit()
    db.refresh(share)
    return share

@router.post("/{share_id}/reject", response_model=schemas.ResourceShareOut)
def reject_share(share_id: UUID, db: Session = Depends(get_db), user = Depends(get_current_user)):
    share = db.get(models.ResourceShare, share_id)
    if not share:
        raise HTTPException(status_code=404)
    lab = db.get(models.Lab, share.to_lab)
    if not lab or lab.owner_id != user.id:
        raise HTTPException(status_code=403)
    share.status = "rejected"
    db.commit()
    db.refresh(share)
    return share
