from uuid import UUID
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends
from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas, audit

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/", response_model=list[schemas.AuditLogOut])
async def list_logs(
    user_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.AuditLog)
    if user_id:
        query = query.filter(models.AuditLog.user_id == user_id)
    else:
        query = query.filter(models.AuditLog.user_id == current_user.id)
    return query.order_by(models.AuditLog.created_at.desc()).all()


@router.get("/report", response_model=list[schemas.AuditReportItem])
async def audit_report(
    start: datetime,
    end: datetime,
    user_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if user_id is None:
        user_id = current_user.id
    data = audit.generate_report(db, start, end, user_id)
    return data
