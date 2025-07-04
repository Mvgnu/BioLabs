from uuid import UUID
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas

router = APIRouter(prefix="/api/notifications", tags=["notifications"])

@router.get("/", response_model=list[schemas.NotificationOut])
async def list_notifications(
    is_read: Optional[bool] = Query(None, description="Filter by read status"),
    category: Optional[str] = Query(None, description="Filter by category"),
    date_from: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    query = db.query(models.Notification).filter(models.Notification.user_id == user.id)
    
    if is_read is not None:
        query = query.filter(models.Notification.is_read == is_read)
    
    if category:
        query = query.filter(models.Notification.category == category)
    
    if date_from:
        try:
            from_date = datetime.strptime(date_from, "%Y-%m-%d")
            query = query.filter(models.Notification.created_at >= from_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_from format")
    
    if date_to:
        try:
            to_date = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
            query = query.filter(models.Notification.created_at < to_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_to format")
    
    return query.order_by(models.Notification.created_at.desc()).all()


@router.post("/{notification_id}/read", response_model=schemas.NotificationOut)
async def mark_read(
    notification_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    notif = (
        db.query(models.Notification)
        .filter_by(id=notification_id, user_id=user.id)
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    db.refresh(notif)
    return notif


@router.post("/mark-all-read")
async def mark_all_read(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Mark all unread notifications as read"""
    db.query(models.Notification).filter(
        and_(
            models.Notification.user_id == user.id,
            models.Notification.is_read == False
        )
    ).update({"is_read": True})
    db.commit()
    return {"message": "All notifications marked as read"}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Delete a notification"""
    notif = (
        db.query(models.Notification)
        .filter_by(id=notification_id, user_id=user.id)
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    
    db.delete(notif)
    db.commit()
    return {"message": "Notification deleted"}


@router.get("/stats")
async def get_notification_stats(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Get notification statistics"""
    notifications = db.query(models.Notification).filter(
        models.Notification.user_id == user.id
    ).all()
    
    stats = {
        "total": len(notifications),
        "unread": len([n for n in notifications if not n.is_read]),
        "by_category": {
            "inventory": 0,
            "protocols": 0,
            "projects": 0,
            "bookings": 0,
            "system": 0,
            "collaboration": 0,
            "compliance": 0,
            "equipment": 0,
            "marketplace": 0,
        },
        "by_priority": {
            "low": 0,
            "medium": 0,
            "high": 0,
            "urgent": 0,
        }
    }
    
    for notification in notifications:
        if notification.category and notification.category in stats["by_category"]:
            stats["by_category"][notification.category] += 1
        
        if notification.priority in stats["by_priority"]:
            stats["by_priority"][notification.priority] += 1
    
    return stats


@router.get("/preferences", response_model=list[schemas.NotificationPreferenceOut])
async def list_preferences(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return db.query(models.NotificationPreference).filter_by(user_id=user.id).all()


@router.put(
    "/preferences/{pref_type}/{channel}",
    response_model=schemas.NotificationPreferenceOut,
)
async def set_preference(
    pref_type: str,
    channel: str,
    pref: schemas.NotificationPreferenceUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    obj = (
        db.query(models.NotificationPreference)
        .filter_by(user_id=user.id, pref_type=pref_type, channel=channel)
        .first()
    )
    if obj:
        obj.enabled = pref.enabled
    else:
        obj = models.NotificationPreference(
            user_id=user.id,
            pref_type=pref_type,
            channel=channel,
            enabled=pref.enabled,
        )
        db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.post("/create", response_model=schemas.NotificationOut)
async def create_notification(
    notification: schemas.NotificationCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Create a new notification (for testing or system use)"""
    # Only allow creating notifications for the current user or if user is admin
    if notification.user_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized to create notifications for other users")
    
    db_notification = models.Notification(**notification.model_dump())
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)
    return db_notification
