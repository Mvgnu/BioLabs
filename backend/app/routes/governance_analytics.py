from __future__ import annotations

from typing import List, Literal
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


@router.get(
    "",
    response_model=(
        schemas.GovernanceAnalyticsReport
        | schemas.GovernanceReviewerCadenceReport
    ),
)
def read_governance_analytics(
    execution_id: UUID | None = Query(default=None),
    limit: int | None = Query(default=50, ge=1, le=200),
    view: Literal["full", "reviewer"] = Query(default="full"),
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

    include_previews = view != "reviewer"

    report = compute_governance_analytics(
        db,
        user,
        team_ids=team_ids,
        execution_ids=execution_ids,
        limit=limit,
        include_previews=include_previews,
    )

    if view == "reviewer":
        totals = report.totals
        cadence_totals = schemas.build_reviewer_cadence_totals(
            reviewer_count=totals.reviewer_count,
            streak_alert_count=totals.streak_alert_count,
            reviewer_latency_p50_minutes=totals.reviewer_latency_p50_minutes,
            reviewer_latency_p90_minutes=totals.reviewer_latency_p90_minutes,
            load_band_counts=totals.reviewer_load_band_counts,
        )
        return schemas.build_reviewer_cadence_report(
            report.reviewer_cadence,
            cadence_totals,
        )

    return report
