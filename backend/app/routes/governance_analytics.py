from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..analytics.governance import compute_governance_analytics
from ..auth import get_current_user
from ..database import get_db
from .experiment_console import _ensure_execution_access, _get_user_team_ids

router = APIRouter(prefix="/api/governance/analytics", tags=["governance-analytics"])

# purpose: expose governance analytics aggregates for experiment console dashboards
# inputs: optional execution id, query limit, authenticated user context
# outputs: GovernanceAnalyticsReport payloads filtered by RBAC constraints
# status: pilot


@router.get("", response_model=schemas.GovernanceAnalyticsReport)
def read_governance_analytics(
    execution_id: UUID | None = Query(default=None),
    limit: int | None = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.GovernanceAnalyticsReport:
    """Return governance preview analytics scoped to authorised executions."""

    team_ids = _get_user_team_ids(db, user)

    execution_ids: List[UUID] | None = None
    if execution_id:
        execution = db.get(models.ProtocolExecution, execution_id)
        if execution is None:
            raise HTTPException(status_code=404, detail="Execution not found")
        _ensure_execution_access(db, execution, user, team_ids)
        execution_ids = [execution_id]

    return compute_governance_analytics(
        db,
        user,
        team_ids=team_ids,
        execution_ids=execution_ids,
        limit=limit,
    )
