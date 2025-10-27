"""Reviewer cadence aggregation helpers for governance analytics and recommendations."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from math import ceil, floor
from statistics import mean
from typing import Iterable, Mapping, MutableMapping, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from .. import models, schemas

# purpose: shareable reviewer cadence utilities powering analytics, overrides, and forecasting
# inputs: reviewer lifecycle samples, RBAC context, SQLAlchemy session
# outputs: normalised GovernanceReviewerCadenceSummary payloads with aggregated guardrails
# status: pilot

REVIEWER_LATENCY_BANDS: tuple[tuple[str, int | None, int | None], ...] = (
    ("under_2h", None, 120),
    ("two_to_eight_h", 120, 480),
    ("eight_to_day", 480, 1440),
    ("over_day", 1440, None),
)

REVIEWER_LOAD_RANK = {"saturated": 3, "steady": 2, "light": 1}


@dataclass
class ReviewerCadenceAccumulator:
    """Mutable collector for reviewer cadence statistics."""

    assigned: int = 0
    completed: int = 0
    pending: int = 0
    latency_samples: list[float] = field(default_factory=list)
    latency_band_counts: MutableMapping[str, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    blocked_samples: list[float] = field(default_factory=list)
    churn_samples: list[float] = field(default_factory=list)
    rollback_precursors: int = 0
    publish_dates: list[datetime] = field(default_factory=list)


def ensure_reviewer_stat(
    stats_map: MutableMapping[UUID, ReviewerCadenceAccumulator],
    reviewer_id: UUID,
) -> ReviewerCadenceAccumulator:
    """Return an accumulator for the given reviewer, creating when absent."""

    accumulator = stats_map.get(reviewer_id)
    if accumulator is None:
        accumulator = ReviewerCadenceAccumulator()
        stats_map[reviewer_id] = accumulator
    return accumulator


def _calculate_percentile(samples: Sequence[float], percentile: float) -> float | None:
    """Return percentile estimate for provided samples using linear interpolation."""

    if not samples:
        return None
    ordered = sorted(samples)
    if not ordered:
        return None
    clamped = max(0.0, min(100.0, percentile))
    if clamped == 0.0:
        return float(ordered[0])
    if clamped == 100.0:
        return float(ordered[-1])
    rank = (clamped / 100.0) * (len(ordered) - 1)
    lower_index = floor(rank)
    upper_index = min(ceil(rank), len(ordered) - 1)
    lower_value = float(ordered[lower_index])
    upper_value = float(ordered[upper_index])
    if lower_index == upper_index:
        return lower_value
    fraction = rank - lower_index
    return lower_value + (upper_value - lower_value) * fraction


def _determine_load_band(assignment_count: int, pending_count: int) -> str:
    """Classify reviewer cadence load using assignment and pending volumes."""

    if pending_count >= 8 or assignment_count >= 12:
        return "saturated"
    if pending_count >= 4 or assignment_count >= 6:
        return "steady"
    return "light"


def _build_latency_band_payload(
    counts: Mapping[str, int]
) -> list[schemas.GovernanceAnalyticsLatencyBand]:
    """Convert latency histogram counts into structured band payloads."""

    payload: list[schemas.GovernanceAnalyticsLatencyBand] = []
    for label, start, end in REVIEWER_LATENCY_BANDS:
        payload.append(
            schemas.GovernanceAnalyticsLatencyBand(
                label=label,
                start_minutes=start,
                end_minutes=end,
                count=counts.get(label, 0),
            )
        )
    return payload


def _calculate_publish_streak(
    published_at_values: Iterable[datetime],
) -> tuple[int, datetime | None]:
    """Determine the contiguous publish streak (<=72h gaps) for a reviewer."""

    ordered = sorted([value for value in published_at_values if isinstance(value, datetime)])
    if not ordered:
        return 0, None
    streak = 1
    last_value = ordered[-1]
    threshold_seconds = 72 * 60 * 60
    for candidate in reversed(ordered[:-1]):
        delta_seconds = (last_value - candidate).total_seconds()
        if delta_seconds <= threshold_seconds:
            streak += 1
            last_value = candidate
        else:
            break
    return streak, ordered[-1]


def build_reviewer_cadence_report(
    db: Session,
    stats: Mapping[UUID, ReviewerCadenceAccumulator],
    requester: models.User,
    membership_ids: Iterable[UUID] | None = None,
) -> schemas.GovernanceReviewerCadenceReport:
    """Return RBAC-filtered reviewer cadence report from aggregated stats."""

    reviewer_ids = list(stats.keys())
    if not reviewer_ids:
        totals = schemas.build_reviewer_cadence_totals(
            reviewer_count=0,
            streak_alert_count=0,
            reviewer_latency_p50_minutes=None,
            reviewer_latency_p90_minutes=None,
            load_band_counts=schemas.build_reviewer_load_band_counts(),
        )
        return schemas.build_reviewer_cadence_report([], totals)

    reviewer_users = {
        user.id: user
        for user in db.query(models.User)
        .filter(models.User.id.in_(reviewer_ids))
        .all()
    }

    membership_set = set(membership_ids or [])
    if requester.is_admin or not membership_set:
        allowed_reviewer_ids = set(reviewer_ids)
    else:
        allowed_reviewer_ids = {
            membership.user_id
            for membership in db.query(models.TeamMember)
            .filter(models.TeamMember.team_id.in_(list(membership_set)))
            .all()
        }
        allowed_reviewer_ids.add(requester.id)

    load_band_totals = {"light": 0, "steady": 0, "saturated": 0}
    global_latency_samples: list[float] = []
    streak_alert_count = 0
    reviewers: list[schemas.GovernanceReviewerCadenceSummary] = []

    for reviewer_id, accumulator in stats.items():
        if reviewer_id not in allowed_reviewer_ids:
            continue
        user = reviewer_users.get(reviewer_id)
        latency_samples = list(accumulator.latency_samples)
        average_latency = mean(latency_samples) if latency_samples else None
        latency_payload = _build_latency_band_payload(accumulator.latency_band_counts)
        blocked_ratio_sample = (
            mean(accumulator.blocked_samples)
            if accumulator.blocked_samples
            else None
        )
        churn_sample = (
            mean(accumulator.churn_samples)
            if accumulator.churn_samples
            else None
        )
        streak, last_publish = _calculate_publish_streak(accumulator.publish_dates)
        streak_alert = streak >= 3
        if streak_alert:
            streak_alert_count += 1
        load_band = _determine_load_band(accumulator.assigned, accumulator.pending)
        load_band_totals[load_band] = load_band_totals.get(load_band, 0) + 1
        global_latency_samples.extend(latency_samples)

        reviewers.append(
            schemas.build_reviewer_cadence_summary(
                reviewer_id=reviewer_id,
                reviewer_email=getattr(user, "email", None),
                reviewer_name=getattr(user, "full_name", None),
                assignment_count=accumulator.assigned,
                completion_count=accumulator.completed,
                pending_count=accumulator.pending,
                load_band=load_band,
                average_latency_minutes=average_latency,
                latency_p50_minutes=_calculate_percentile(latency_samples, 50.0),
                latency_p90_minutes=_calculate_percentile(latency_samples, 90.0),
                latency_bands=latency_payload,
                blocked_ratio_trailing=blocked_ratio_sample,
                churn_signal=churn_sample,
                rollback_precursor_count=accumulator.rollback_precursors,
                publish_streak=streak,
                last_publish_at=last_publish,
                streak_alert=streak_alert,
            )
        )

    reviewers.sort(
        key=lambda item: (
            REVIEWER_LOAD_RANK.get(item.load_band, 0),
            item.completion_count,
        ),
        reverse=True,
    )

    totals = schemas.build_reviewer_cadence_totals(
        reviewer_count=len(reviewers),
        streak_alert_count=streak_alert_count,
        reviewer_latency_p50_minutes=_calculate_percentile(global_latency_samples, 50.0),
        reviewer_latency_p90_minutes=_calculate_percentile(global_latency_samples, 90.0),
        load_band_counts=schemas.build_reviewer_load_band_counts(**load_band_totals),
    )

    return schemas.build_reviewer_cadence_report(reviewers, totals)

