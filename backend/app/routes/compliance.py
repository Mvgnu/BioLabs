from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from uuid import UUID

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas

router = APIRouter(prefix="/api/compliance", tags=["compliance"])

@router.post("/records", response_model=schemas.ComplianceRecordOut)
async def create_record(
    rec: schemas.ComplianceRecordCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    obj = models.ComplianceRecord(
        item_id=rec.item_id,
        record_type=rec.record_type,
        status=rec.status,
        notes=rec.notes,
        user_id=user.id,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/records", response_model=list[schemas.ComplianceRecordOut])
async def list_records(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return db.query(models.ComplianceRecord).all()


@router.put("/records/{record_id}", response_model=schemas.ComplianceRecordOut)
async def update_record(
    record_id: UUID,
    data: schemas.ComplianceRecordUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    obj = db.query(models.ComplianceRecord).filter_by(id=record_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Record not found")
    if data.status is not None:
        obj.status = data.status
    if data.notes is not None:
        obj.notes = data.notes
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/summary")
async def compliance_summary(db: Session = Depends(get_db), user: models.User = Depends(get_current_user)):
    rows = db.query(models.ComplianceRecord.status, func.count(models.ComplianceRecord.id)).group_by(models.ComplianceRecord.status).all()
    return [{"status": r[0], "count": r[1]} for r in rows]
