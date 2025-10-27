from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..recommendations.governance import generate_override_recommendations
from .experiment_console import _ensure_execution_access, _get_user_team_ids

router = APIRouter(
    prefix="/api/governance/recommendations",
    tags=["governance-recommendations"],
)

# purpose: expose governance override recommendations scoped by RBAC and execution access
# inputs: optional execution identifier, pagination limit, authenticated user context
# outputs: GovernanceOverrideRecommendationReport payload with staffing advisories
# status: pilot


@router.get(
    "/override",
    response_model=schemas.GovernanceOverrideRecommendationReport,
)
def read_governance_override_recommendations(
    execution_id: UUID | None = Query(default=None),
    limit: int | None = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.GovernanceOverrideRecommendationReport:
    """Return override recommendations for governance operators."""

    team_ids = _get_user_team_ids(db, user)

    execution_ids: list[UUID] | None = None
    if execution_id:
        execution = db.get(models.ProtocolExecution, execution_id)
        if execution is None:
            raise HTTPException(status_code=404, detail="Execution not found")
        _ensure_execution_access(db, execution, user, team_ids)
        execution_ids = [execution_id]

    report = generate_override_recommendations(
        db,
        user,
        team_ids=team_ids,
        execution_ids=execution_ids,
        limit=limit,
    )

    db.flush()
    return report

