from datetime import datetime
from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, HTTPException

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas, notify

router = APIRouter(prefix="/api/schedule", tags=["schedule"])

@router.post("/resources", response_model=schemas.ResourceOut)
async def create_resource(
    resource: schemas.ResourceCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    db_res = models.Resource(**resource.model_dump(), created_by=user.id)
    db.add(db_res)
    db.commit()
    db.refresh(db_res)
    return db_res


@router.get("/resources", response_model=list[schemas.ResourceOut])
async def list_resources(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return db.query(models.Resource).all()


@router.post("/bookings", response_model=schemas.BookingOut)
async def create_booking(
    booking: schemas.BookingCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if booking.start_time >= booking.end_time:
        raise HTTPException(status_code=400, detail="Invalid time range")
    overlaps = (
        db.query(models.Booking)
        .filter(models.Booking.resource_id == booking.resource_id)
        .filter(models.Booking.end_time > booking.start_time)
        .filter(models.Booking.start_time < booking.end_time)
        .first()
    )
    if overlaps:
        raise HTTPException(status_code=400, detail="Time slot unavailable")
    db_booking = models.Booking(**booking.model_dump(), user_id=user.id)
    resource = (
        db.query(models.Resource)
        .filter(models.Resource.id == booking.resource_id)
        .first()
    )
    if resource:
        message = (
            f"{user.email} booked {resource.name} from {booking.start_time} to {booking.end_time}"
        )
        # in-app notification
        pref_in_app = (
            db.query(models.NotificationPreference)
            .filter_by(
                user_id=resource.created_by,
                pref_type="booking",
                channel="in_app",
            )
            .first()
        )
        if not pref_in_app or pref_in_app.enabled:
            notif = models.Notification(
                user_id=resource.created_by,
                message=message,
            )
            db.add(notif)

        owner = db.query(models.User).filter_by(id=resource.created_by).first()
        if owner:
            # email
            pref_email = (
                db.query(models.NotificationPreference)
                .filter_by(
                    user_id=resource.created_by,
                    pref_type="booking",
                    channel="email",
                )
                .first()
            )
            if (not pref_email or pref_email.enabled) and owner.email:
                notify.send_email(owner.email, "Booking notification", message)

            # sms
            pref_sms = (
                db.query(models.NotificationPreference)
                .filter_by(
                    user_id=resource.created_by,
                    pref_type="booking",
                    channel="sms",
                )
                .first()
            )
            if (not pref_sms or pref_sms.enabled) and owner.phone_number:
                notify.send_sms(owner.phone_number, message)
    db.add(db_booking)
    db.commit()
    db.refresh(db_booking)
    return db_booking


@router.get("/bookings", response_model=list[schemas.BookingOut])
async def list_bookings(
    resource_id: UUID | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    q = db.query(models.Booking)
    if resource_id:
        q = q.filter(models.Booking.resource_id == resource_id)
    return q.all()

