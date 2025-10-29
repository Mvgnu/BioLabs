"""API routes for custody and freezer governance."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..services import sample_governance

# purpose: expose custody governance endpoints for freezer topology and ledger actions
# status: pilot
# depends_on: backend.app.services.sample_governance

router = APIRouter(prefix="/api/governance/custody", tags=["governance", "custody"])


def _require_operator(user: models.User) -> None:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Custody governance access requires administrator privileges",
        )


@router.get("/freezers", response_model=list[schemas.FreezerUnitTopology])
def get_freezer_topology(
    team_id: UUID | None = None,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _require_operator(user)
    return sample_governance.list_freezer_topology(db, team_id=team_id)


@router.get("/logs", response_model=list[schemas.SampleCustodyLogOut])
def list_custody_logs(
    asset_id: UUID | None = None,
    asset_version_id: UUID | None = None,
    planner_session_id: UUID | None = None,
    compartment_id: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _require_operator(user)
    logs = sample_governance.fetch_custody_logs(
        db,
        asset_id=asset_id,
        asset_version_id=asset_version_id,
        planner_session_id=planner_session_id,
        compartment_id=compartment_id,
        limit=limit,
    )
    return logs


@router.post(
    "/logs",
    status_code=status.HTTP_201_CREATED,
    response_model=schemas.SampleCustodyLogOut,
)
def create_custody_log(
    entry: schemas.SampleCustodyLogCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    _require_operator(user)
    log = sample_governance.record_custody_event(db, entry, actor_id=user.id)
    db.refresh(log)
    return log
