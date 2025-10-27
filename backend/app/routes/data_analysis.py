from __future__ import annotations

from datetime import datetime
from typing import Literal

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session
from uuid import UUID

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db

router = APIRouter(prefix="/api/data", tags=["data"])


@router.post("/summary")
def csv_summary(upload: UploadFile = File(...), user=Depends(get_current_user)):
    df = pd.read_csv(upload.file)
    # return describe dictionary for numeric columns
    summary = df.describe().to_dict()
    return summary


EVIDENCE_EVENT_PREFIX: dict[str, str] = {
    "analytics_snapshot": "analytics.snapshot",
    "qc_metric": "qc.metric",
    "remediation_report": "remediation.report",
}


@router.get("/evidence", response_model=schemas.NarrativeEvidencePage)
def list_data_evidence(
    domain: Literal["analytics_snapshot", "qc_metric", "remediation_report"] = "analytics_snapshot",
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    execution_id: str | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    prefix = EVIDENCE_EVENT_PREFIX[domain]
    query = (
        db.query(models.ExecutionEvent)
        .filter(models.ExecutionEvent.event_type.startswith(prefix))
        .order_by(models.ExecutionEvent.created_at.desc())
    )
    if execution_id:
        try:
            exec_uuid = UUID(execution_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid execution id filter") from exc
        query = query.filter(models.ExecutionEvent.execution_id == exec_uuid)

    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid cursor") from exc
        query = query.filter(models.ExecutionEvent.created_at < cursor_dt)

    events = query.limit(limit + 1).all()
    has_more = len(events) > limit
    if has_more:
        events = events[:limit]

    next_cursor = None
    if has_more and events:
        tail = events[-1]
        if tail.created_at:
            next_cursor = tail.created_at.isoformat()

    descriptors: list[schemas.NarrativeEvidenceDescriptor] = []
    for event in events:
        payload = event.payload or {}
        label = None
        if isinstance(payload, dict):
            label = payload.get("label") or payload.get("title")
        if not label:
            label = f"{domain.replace('_', ' ').title()} @ {event.created_at.isoformat()}"
        descriptor = schemas.NarrativeEvidenceDescriptor(
            id=event.id,
            type=domain,
            label=label,
            snapshot={
                "event_type": event.event_type,
                "created_at": event.created_at.isoformat() if event.created_at else None,
                "payload": payload,
            },
            context={
                "execution_id": str(event.execution_id) if event.execution_id else None,
                "attempt": payload.get("attempt") if isinstance(payload, dict) else None,
            },
        )
        descriptors.append(descriptor)

    return schemas.NarrativeEvidencePage(items=descriptors, next_cursor=next_cursor)
