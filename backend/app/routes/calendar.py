from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from ..database import get_db
from ..models import CalendarEvent
from ..schemas import CalendarEventCreate, CalendarEventOut, CalendarEventUpdate
from ..auth import get_current_user

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.post("", response_model=CalendarEventOut)
def create_event(event: CalendarEventCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    db_event = CalendarEvent(**event.model_dump(), created_by=user.id)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


@router.get("", response_model=list[CalendarEventOut])
def list_events(db: Session = Depends(get_db), user=Depends(get_current_user)):
    return db.query(CalendarEvent).all()


@router.put("/{event_id}", response_model=CalendarEventOut)
def update_event(
    event_id: UUID,
    data: CalendarEventUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    ev = db.get(CalendarEvent, event_id)
    if not ev:
        raise HTTPException(status_code=404)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(ev, k, v)
    db.commit()
    db.refresh(ev)
    return ev


@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: UUID, db: Session = Depends(get_db), user=Depends(get_current_user)):
    ev = db.get(CalendarEvent, event_id)
    if not ev:
        raise HTTPException(status_code=404)
    db.delete(ev)
    db.commit()
    return
