from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func
from . import models


def log_action(
    db: Session,
    user_id: str | UUID,
    action: str,
    target_type: str | None = None,
    target_id: str | UUID | None = None,
    details: dict | None = None,
):
    log = models.AuditLog(
        user_id=UUID(str(user_id)),
        action=action,
        target_type=target_type,
        target_id=UUID(str(target_id)) if target_id else None,
        details=details or {},
        created_at=datetime.now(timezone.utc),
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def generate_report(
    db: Session,
    start: datetime,
    end: datetime,
    user_id: UUID | None = None,
):
    query = db.query(models.AuditLog).filter(
        models.AuditLog.created_at >= start,
        models.AuditLog.created_at <= end,
    )
    if user_id:
        query = query.filter(models.AuditLog.user_id == user_id)
    rows = (
        query.with_entities(models.AuditLog.action, func.count(models.AuditLog.id))
        .group_by(models.AuditLog.action)
        .all()
    )
    return [{"action": r[0], "count": r[1]} for r in rows]
