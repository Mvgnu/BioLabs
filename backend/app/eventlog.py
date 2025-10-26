"""Utilities for recording execution timeline events."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from . import models

# purpose: shareable helpers for persisting execution timeline events across services
# inputs: SQLAlchemy session, protocol execution instance, event metadata
# outputs: normalized ExecutionEvent rows with sequential ordering
# status: pilot


def record_execution_event(
    db: Session,
    execution: models.ProtocolExecution,
    event_type: str,
    payload: dict[str, Any],
    actor: models.User | None = None,
) -> models.ExecutionEvent:
    """Persist a structured execution event for timeline replay."""

    payload_dict = payload if isinstance(payload, dict) else {}
    latest = (
        db.query(models.ExecutionEvent)
        .filter(models.ExecutionEvent.execution_id == execution.id)
        .order_by(models.ExecutionEvent.sequence.desc())
        .first()
    )
    next_sequence = 1 if latest is None else latest.sequence + 1
    event = models.ExecutionEvent(
        execution_id=execution.id,
        event_type=event_type,
        payload=payload_dict,
        actor_id=getattr(actor, "id", None),
        sequence=next_sequence,
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    return event

