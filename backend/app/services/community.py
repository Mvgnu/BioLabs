from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Iterable, Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from .. import models, schemas

# purpose: orchestrate community discovery portfolios, guardrail-aware feeds, and moderation flows
# status: experimental
# depends_on: backend.app.models (CommunityPortfolio, DNAAsset, ProtocolTemplate, CloningPlannerSession)
# related_docs: docs/community/README.md


def list_portfolios(
    db: Session,
    *,
    include_unpublished: bool = False,
    visibility: str | None = "public",
) -> list[models.CommunityPortfolio]:
    """Return community portfolios filtered by visibility and publication state."""

    query = db.query(models.CommunityPortfolio)
    if visibility:
        query = query.filter(models.CommunityPortfolio.visibility == visibility)
    if not include_unpublished:
        query = query.filter(models.CommunityPortfolio.status != "draft")
    return (
        query.order_by(
            models.CommunityPortfolio.engagement_score.desc(),
            models.CommunityPortfolio.published_at.desc().nullslast(),
        )
        .limit(50)
        .all()
    )


def create_portfolio(
    db: Session,
    payload: schemas.CommunityPortfolioCreate,
    *,
    creator_id: UUID,
    team_id: UUID | None,
) -> models.CommunityPortfolio:
    """Create a portfolio with aggregated provenance and guardrail lineage."""

    portfolio = models.CommunityPortfolio(
        slug=payload.slug,
        title=payload.title,
        summary=payload.summary,
        visibility=payload.visibility,
        license=payload.license,
        tags=payload.tags,
        attribution=payload.attribution,
        provenance=payload.provenance,
        mitigation_history=payload.mitigation_history,
        replay_checkpoints=payload.replay_checkpoints,
        team_id=team_id,
        created_by_id=creator_id,
        status="draft",
        guardrail_flags=[],
        engagement_score=0.0,
    )
    db.add(portfolio)
    db.flush()
    if payload.assets:
        for asset in payload.assets:
            add_asset(db, portfolio, asset, actor_id=creator_id)
    _finalize_portfolio_state(portfolio)
    db.add(portfolio)
    return portfolio


def add_asset(
    db: Session,
    portfolio: models.CommunityPortfolio,
    asset_payload: schemas.CommunityPortfolioAssetRef,
    *,
    actor_id: UUID | None = None,
) -> models.CommunityPortfolio:
    """Attach an asset link and refresh guardrail provenance."""

    guardrail_snapshot = _derive_guardrail_snapshot(db, asset_payload)
    link = models.CommunityPortfolioAssetLink(
        portfolio_id=portfolio.id,
        asset_type=asset_payload.asset_type,
        asset_id=asset_payload.asset_id,
        asset_version_id=asset_payload.asset_version_id,
        planner_session_id=asset_payload.planner_session_id,
        meta=asset_payload.meta,
        guardrail_snapshot=guardrail_snapshot,
    )
    db.add(link)
    db.flush()
    _refresh_portfolio_lineage(db, portfolio)
    portfolio.updated_at = datetime.now(timezone.utc)
    if portfolio.status == "draft" and not portfolio.guardrail_flags:
        portfolio.status = "published"
        portfolio.published_at = datetime.now(timezone.utc)
    elif portfolio.guardrail_flags:
        portfolio.status = "requires_review"
    db.add(portfolio)
    return portfolio


def record_engagement(
    db: Session,
    portfolio: models.CommunityPortfolio,
    *,
    user_id: UUID,
    payload: schemas.CommunityPortfolioEngagementCreate,
) -> models.CommunityPortfolioEngagement:
    """Upsert engagement signal and refresh scoring."""

    weight = payload.weight if payload.weight is not None else _default_weight(payload.interaction)
    engagement = (
        db.query(models.CommunityPortfolioEngagement)
        .filter(
            models.CommunityPortfolioEngagement.portfolio_id == portfolio.id,
            models.CommunityPortfolioEngagement.user_id == user_id,
            models.CommunityPortfolioEngagement.interaction == payload.interaction,
        )
        .first()
    )
    if engagement:
        engagement.weight = weight
        engagement.created_at = datetime.now(timezone.utc)
    else:
        engagement = models.CommunityPortfolioEngagement(
            portfolio_id=portfolio.id,
            user_id=user_id,
            interaction=payload.interaction,
            weight=weight,
        )
        db.add(engagement)
    db.flush()
    _refresh_engagement_score(db, portfolio)
    return engagement


def create_moderation_event(
    db: Session,
    portfolio: models.CommunityPortfolio,
    *,
    actor_id: UUID | None,
    decision: schemas.CommunityModerationDecision,
) -> models.CommunityModerationEvent:
    """Persist a guardrail moderation outcome and update portfolio status."""

    event = models.CommunityModerationEvent(
        portfolio_id=portfolio.id,
        triggered_by_id=actor_id,
        guardrail_flags=list(portfolio.guardrail_flags or []),
        outcome=decision.outcome,
        notes=decision.notes,
    )
    db.add(event)
    if decision.outcome == "cleared":
        portfolio.guardrail_flags = []
        portfolio.status = "published"
        if not portfolio.published_at:
            portfolio.published_at = datetime.now(timezone.utc)
    elif decision.outcome == "requires_mitigation":
        portfolio.status = "requires_review"
    else:
        portfolio.status = "blocked"
    portfolio.updated_at = datetime.now(timezone.utc)
    db.add(portfolio)
    return event


def personal_feed(
    db: Session,
    *,
    user_id: UUID,
    limit: int = 10,
) -> list[schemas.CommunityFeedEntry]:
    """Generate a personalized feed ranked by engagement and guardrail readiness."""

    base_query = (
        db.query(models.CommunityPortfolio)
        .filter(
            models.CommunityPortfolio.visibility == "public",
            models.CommunityPortfolio.status == "published",
        )
        .order_by(
            models.CommunityPortfolio.engagement_score.desc(),
            models.CommunityPortfolio.published_at.desc().nullslast(),
        )
        .limit(limit)
    )
    portfolios = base_query.all()
    engagements = _portfolio_engagement_map(db, [p.id for p in portfolios], user_id)
    entries: list[schemas.CommunityFeedEntry] = []
    for portfolio in portfolios:
        reason = "recommended"
        if portfolio.guardrail_flags:
            reason = "awaiting guardrail mitigation"
        elif engagements.get(portfolio.id):
            reason = engagements[portfolio.id]
        score = float(portfolio.engagement_score)
        entries.append(
            schemas.CommunityFeedEntry(
                portfolio=portfolio,
                reason=reason,
                score=score,
            )
        )
    return entries


def trending(
    db: Session,
    *,
    timeframe: str = "7d",
    limit: int = 10,
) -> schemas.CommunityTrendingOut:
    """Aggregate trending portfolios based on engagement deltas."""

    cutoff = datetime.now(timezone.utc) - _timeframe_delta(timeframe)
    subquery = (
        db.query(
            models.CommunityPortfolioEngagement.portfolio_id,
            sa.func.sum(models.CommunityPortfolioEngagement.weight).label("total_weight"),
        )
        .filter(models.CommunityPortfolioEngagement.created_at >= cutoff)
        .group_by(models.CommunityPortfolioEngagement.portfolio_id)
        .subquery()
    )
    rows = (
        db.query(models.CommunityPortfolio, sa.func.coalesce(subquery.c.total_weight, 0.0))
        .outerjoin(subquery, models.CommunityPortfolio.id == subquery.c.portfolio_id)
        .filter(models.CommunityPortfolio.status == "published")
        .order_by(sa.desc(sa.func.coalesce(subquery.c.total_weight, 0.0)))
        .limit(limit)
        .all()
    )
    portfolios = [
        schemas.CommunityTrendingPortfolio(
            portfolio=row[0],
            engagement_delta=float(row[1] or 0.0),
            guardrail_summary=list(row[0].guardrail_flags or []),
        )
        for row in rows
    ]
    return schemas.CommunityTrendingOut(timeframe=timeframe, portfolios=portfolios)


def _refresh_portfolio_lineage(db: Session, portfolio: models.CommunityPortfolio) -> None:
    assets = portfolio.assets
    provenance = defaultdict(list)
    mitigation_history: list[dict[str, str]] = []
    replay_checkpoints: list[dict[str, str]] = []
    guardrail_flags: set[str] = set()
    for link in assets:
        guardrail_flags.update(link.guardrail_snapshot.get("guardrail_flags", []))
        if link.asset_type == "dna_asset":
            asset = db.get(models.DNAAsset, link.asset_id)
            if asset:
                provenance["dna_assets"].append(
                    {
                        "id": str(asset.id),
                        "name": asset.name,
                        "status": asset.status,
                        "latest_version_id": str(asset.latest_version_id) if asset.latest_version_id else None,
                    }
                )
                mitigation_history.extend(
                    _guardrail_events_to_history(asset.guardrail_events)
                )
        elif link.asset_type == "protocol":
            protocol = db.get(models.ProtocolTemplate, link.asset_id)
            if protocol:
                provenance["protocol_templates"].append(
                    {
                        "id": str(protocol.id),
                        "name": protocol.name,
                        "version": protocol.version,
                    }
                )
        elif link.asset_type == "planner_session":
            session = db.get(models.CloningPlannerSession, link.asset_id)
            if session:
                provenance["planner_sessions"].append(
                    {
                        "id": str(session.id),
                        "status": session.status,
                        "assembly_strategy": session.assembly_strategy,
                    }
                )
                replay_checkpoints.append(
                    {
                        "session_id": str(session.id),
                        "checkpoint": session.timeline_cursor,
                        "guardrail_state": session.guardrail_state,
                    }
                )
                mitigation_history.append(
                    {
                        "session_id": str(session.id),
                        "guardrail_state": session.guardrail_state,
                        "last_error": session.last_error,
                    }
                )
    portfolio.provenance = {k: v for k, v in provenance.items()}
    portfolio.mitigation_history = mitigation_history
    portfolio.replay_checkpoints = replay_checkpoints
    portfolio.guardrail_flags = sorted(guardrail_flags)


def _finalize_portfolio_state(portfolio: models.CommunityPortfolio) -> None:
    if portfolio.guardrail_flags:
        portfolio.status = "requires_review"
    else:
        portfolio.status = "published"
        portfolio.published_at = datetime.now(timezone.utc)


def _refresh_engagement_score(db: Session, portfolio: models.CommunityPortfolio) -> None:
    total = (
        db.query(sa.func.coalesce(sa.func.sum(models.CommunityPortfolioEngagement.weight), 0.0))
        .filter(models.CommunityPortfolioEngagement.portfolio_id == portfolio.id)
        .scalar()
    )
    portfolio.engagement_score = float(total or 0.0)
    portfolio.updated_at = datetime.now(timezone.utc)
    db.add(portfolio)


def _derive_guardrail_snapshot(
    db: Session, asset_payload: schemas.CommunityPortfolioAssetRef
) -> dict:
    if asset_payload.asset_type == "dna_asset":
        asset = db.get(models.DNAAsset, asset_payload.asset_id)
        if asset and asset.guardrail_events:
            latest_event = asset.guardrail_events[0]
            details = latest_event.details or {}
            guardrail_flags: list[str] = []
            if isinstance(details, dict):
                raw_flags = details.get("guardrail_flags")
                if isinstance(raw_flags, (list, tuple)):
                    guardrail_flags = [str(flag) for flag in raw_flags]
            return {
                "guardrail_flags": guardrail_flags,
                "event_type": latest_event.event_type,
                "recorded_at": latest_event.created_at.isoformat(),
            }
        return {"guardrail_flags": []}
    if asset_payload.asset_type == "planner_session":
        session = db.get(models.CloningPlannerSession, asset_payload.asset_id)
        if session:
            state = session.guardrail_state or {}
            return {
                "guardrail_flags": state.get("breaches", []) or state.get("flags", []),
                "status": session.status,
                "checkpoint": session.timeline_cursor,
            }
        return {"guardrail_flags": []}
    if asset_payload.asset_type == "protocol":
        protocol = db.get(models.ProtocolTemplate, asset_payload.asset_id)
        if protocol:
            return {
                "version": protocol.version,
                "is_public": protocol.is_public,
                "guardrail_flags": [],
            }
        return {"guardrail_flags": []}
    return {"guardrail_flags": []}


def _portfolio_engagement_map(
    db: Session, portfolio_ids: Sequence[UUID], user_id: UUID
) -> dict[UUID, str]:
    if not portfolio_ids:
        return {}
    rows = (
        db.query(models.CommunityPortfolioEngagement)
        .filter(
            models.CommunityPortfolioEngagement.portfolio_id.in_(portfolio_ids),
            models.CommunityPortfolioEngagement.user_id == user_id,
        )
        .all()
    )
    mapping: dict[UUID, str] = {}
    for row in rows:
        mapping[row.portfolio_id] = row.interaction
    return mapping


def _guardrail_events_to_history(events: Iterable[models.DNAAssetGuardrailEvent]) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []
    for event in events:
        details = event.details or {}
        guardrail_flags: list[str] = []
        if isinstance(details, dict):
            raw_flags = details.get("guardrail_flags")
            if isinstance(raw_flags, (list, tuple)):
                guardrail_flags = [str(flag) for flag in raw_flags]
        history.append(
            {
                "event_type": event.event_type,
                "created_at": event.created_at.isoformat(),
                "guardrail_flags": guardrail_flags,
            }
        )
    return history


def _default_weight(interaction: str) -> float:
    match interaction:
        case "view":
            return 0.2
        case "bookmark":
            return 0.6
        case "review":
            return 0.8
        case "star":
            return 1.0
        case _:
            return 0.1


def _timeframe_delta(timeframe: str):
    if timeframe == "24h":
        return timedelta(hours=24)
    if timeframe == "30d":
        return timedelta(days=30)
    return timedelta(days=7)


