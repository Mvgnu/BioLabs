"""Governance override recommendation rules and helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from .. import models, schemas
from ..analytics.governance import compute_governance_analytics
from ..eventlog import record_governance_recommendation_event

# purpose: derive deterministic override recommendations from reviewer cadence analytics
# inputs: governance analytics report, RBAC context, execution scope, recommendation thresholds
# outputs: GovernanceOverrideRecommendationReport payloads for staffing interventions
# status: pilot

REASSIGN_LATENCY_THRESHOLD = 240.0  # minutes
BLOCKED_RATIO_THRESHOLD = 0.5
CHURN_SIGNAL_THRESHOLD = 2.0


def _generate_recommendation_id(rule_key: str, reviewer_id: UUID | None) -> str:
    reviewer_fragment = str(reviewer_id) if reviewer_id else "global"
    return f"{rule_key}:{reviewer_fragment}"


def _admin_priority(priority: str, is_admin: bool) -> str:
    if not is_admin:
        return priority
    if priority == "low":
        return "medium"
    if priority == "medium":
        return "high"
    return priority


def _build_recommendation_metrics(
    reviewer: schemas.GovernanceReviewerCadenceSummary,
) -> dict[str, float | int | str | None]:
    return {
        "load_band": reviewer.load_band,
        "average_latency_minutes": reviewer.average_latency_minutes,
        "latency_p90_minutes": reviewer.latency_p90_minutes,
        "blocked_ratio_trailing": reviewer.blocked_ratio_trailing,
        "churn_signal": reviewer.churn_signal,
        "publish_streak": reviewer.publish_streak,
        "pending_count": reviewer.pending_count,
        "assignment_count": reviewer.assignment_count,
    }


def _log_recommendations(
    db: Session,
    recommendations: Sequence[schemas.GovernanceOverrideRecommendation],
    executions: Iterable[models.ProtocolExecution],
) -> None:
    for execution in executions:
        if execution is None:
            continue
        for recommendation in recommendations:
            record_governance_recommendation_event(
                db,
                execution,
                recommendation.rule_key,
                recommendation.model_dump(mode="json"),
                actor=None,
                opted_out=not recommendation.allow_opt_out,
            )
            db.flush()


def generate_override_recommendations(
    db: Session,
    user: models.User,
    *,
    team_ids: Iterable[UUID] | None = None,
    execution_ids: Sequence[UUID] | None = None,
    limit: int | None = 50,
) -> schemas.GovernanceOverrideRecommendationReport:
    """Compute governance override recommendations for the requesting user."""

    analytics_report = compute_governance_analytics(
        db,
        user,
        team_ids=set(team_ids or []),
        execution_ids=execution_ids,
        limit=limit,
        include_previews=False,
    )

    generated_at = datetime.now(timezone.utc)
    related_execution_ids = list(execution_ids or [])
    recommendations: list[schemas.GovernanceOverrideRecommendation] = []

    for reviewer in analytics_report.reviewer_cadence:
        metrics = _build_recommendation_metrics(reviewer)
        reviewer_id = reviewer.reviewer_id
        if (
            reviewer.load_band == "saturated"
            and (reviewer.latency_p90_minutes or 0.0) >= REASSIGN_LATENCY_THRESHOLD
        ):
            rule_key = "cadence_overload"
            recommendations.append(
                schemas.build_governance_override_recommendation(
                    recommendation_id=_generate_recommendation_id(rule_key, reviewer_id),
                    rule_key=rule_key,
                    action="reassign",
                    priority=_admin_priority("high", user.is_admin),
                    summary="Reassign reviewer to relieve saturated load",
                    detail=(
                        "Reviewer latency and assignment volume signal a staffing"
                        " overload. Reassign upcoming baselines to balance throughput."
                    ),
                    reviewer_id=reviewer_id,
                    reviewer_name=reviewer.reviewer_name,
                    reviewer_email=reviewer.reviewer_email,
                    triggered_at=generated_at,
                    related_execution_ids=related_execution_ids,
                    metrics=metrics,
                )
            )

        if reviewer.streak_alert:
            rule_key = "streak_cooldown"
            recommendations.append(
                schemas.build_governance_override_recommendation(
                    recommendation_id=_generate_recommendation_id(rule_key, reviewer_id),
                    rule_key=rule_key,
                    action="cooldown",
                    priority=_admin_priority("medium", user.is_admin),
                    summary="Offer cooldown window after rapid publish streak",
                    detail=(
                        "Reviewer has published three or more baselines in rapid"
                        " succession. Offer a cooldown or delegate next review to"
                        " avoid burnout."
                    ),
                    reviewer_id=reviewer_id,
                    reviewer_name=reviewer.reviewer_name,
                    reviewer_email=reviewer.reviewer_email,
                    triggered_at=generated_at,
                    related_execution_ids=related_execution_ids,
                    metrics=metrics,
                )
            )

        blocked_ratio = reviewer.blocked_ratio_trailing or 0.0
        churn_signal = reviewer.churn_signal or 0.0
        if (
            blocked_ratio >= BLOCKED_RATIO_THRESHOLD
            and churn_signal >= CHURN_SIGNAL_THRESHOLD
        ):
            rule_key = "blocker_churn_escalation"
            recommendations.append(
                schemas.build_governance_override_recommendation(
                    recommendation_id=_generate_recommendation_id(rule_key, reviewer_id),
                    rule_key=rule_key,
                    action="escalate",
                    priority=_admin_priority("high", user.is_admin),
                    summary="Escalate blocker churn to governance admins",
                    detail=(
                        "Blocked ratio and churn signal indicate recurring rollout"
                        " risk. Escalate to governance admins for override guidance."
                    ),
                    reviewer_id=reviewer_id,
                    reviewer_name=reviewer.reviewer_name,
                    reviewer_email=reviewer.reviewer_email,
                    triggered_at=generated_at,
                    related_execution_ids=related_execution_ids,
                    metrics={**metrics, "blocked_ratio": blocked_ratio, "churn": churn_signal},
                )
            )

    report = schemas.build_governance_override_report(
        generated_at=generated_at, recommendations=recommendations
    )

    if recommendations and related_execution_ids:
        execution_records = [
            db.get(models.ProtocolExecution, execution_id)
            for execution_id in related_execution_ids
        ]
        _log_recommendations(db, recommendations, execution_records)

    return report

