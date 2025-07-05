from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas

router = APIRouter(prefix="/api/labs", tags=["labs"])


@router.post("", response_model=schemas.LabOut)
def create_lab(
    lab: schemas.LabCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    db_lab = models.Lab(**lab.model_dump(), owner_id=user.id)
    db.add(db_lab)
    db.commit()
    db.refresh(db_lab)
    return db_lab


@router.get("", response_model=List[schemas.LabOut])
def list_labs(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(models.Lab).all()


@router.post("/{lab_id}/connections", response_model=schemas.LabConnectionOut)
def request_connection(
    lab_id: UUID,
    data: schemas.LabConnectionCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    lab = db.get(models.Lab, lab_id)
    if not lab or lab.owner_id != user.id:
        raise HTTPException(status_code=404)
    conn = models.LabConnection(from_lab=lab_id, to_lab=data.target_lab)
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


@router.post("/connections/{connection_id}/accept", response_model=schemas.LabConnectionOut)
def accept_connection(
    connection_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    conn = db.get(models.LabConnection, connection_id)
    if not conn:
        raise HTTPException(status_code=404)
    lab = db.get(models.Lab, conn.to_lab)
    if not lab or lab.owner_id != user.id:
        raise HTTPException(status_code=403)
    conn.status = "accepted"
    db.commit()
    db.refresh(conn)
    return conn


@router.get("/connections", response_model=List[schemas.LabConnectionOut])
def list_connections(db: Session = Depends(get_db), user=Depends(get_current_user)):
    labs = db.query(models.Lab).filter(models.Lab.owner_id == user.id).all()
    ids = [l.id for l in labs]
    if not ids:
        return []
    return (
        db.query(models.LabConnection)
        .filter(models.LabConnection.from_lab.in_(ids) | models.LabConnection.to_lab.in_(ids))
        .all()
    )
