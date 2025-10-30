from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..services import community as community_service

router = APIRouter(prefix="/api/community", tags=["community"])


@router.get("/portfolios", response_model=list[schemas.CommunityPortfolioOut])
async def list_portfolios(
    include_unpublished: bool = Query(False),
    visibility: str | None = Query("public"),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    portfolios = community_service.list_portfolios(
        db,
        include_unpublished=include_unpublished and user.is_admin,
        visibility=visibility if visibility in {"public", "restricted"} else None,
    )
    return portfolios


@router.post("/portfolios", response_model=schemas.CommunityPortfolioOut)
async def create_portfolio(
    payload: schemas.CommunityPortfolioCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    team_id = user.teams[0].team_id if user.teams else None
    portfolio = community_service.create_portfolio(
        db,
        payload,
        creator_id=user.id,
        team_id=team_id,
    )
    db.commit()
    db.refresh(portfolio)
    return portfolio


@router.get("/portfolios/{portfolio_id}", response_model=schemas.CommunityPortfolioOut)
async def get_portfolio(
    portfolio_id: UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    portfolio = db.get(models.CommunityPortfolio, portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    if portfolio.visibility != "public" and portfolio.created_by_id != user.id and not user.is_admin:
        raise HTTPException(status_code=403, detail="Portfolio restricted")
    return portfolio


@router.post("/portfolios/{portfolio_id}/assets", response_model=schemas.CommunityPortfolioOut)
async def add_portfolio_asset(
    portfolio_id: UUID,
    payload: schemas.CommunityPortfolioAssetRef,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    portfolio = db.get(models.CommunityPortfolio, portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    if portfolio.created_by_id not in {None, user.id} and not user.is_admin:
        raise HTTPException(status_code=403, detail="Not allowed to modify portfolio")
    portfolio = community_service.add_asset(db, portfolio, payload, actor_id=user.id)
    db.commit()
    db.refresh(portfolio)
    return portfolio


@router.post(
    "/portfolios/{portfolio_id}/engagements",
    response_model=schemas.CommunityPortfolioEngagementOut,
)
async def record_engagement(
    portfolio_id: UUID,
    payload: schemas.CommunityPortfolioEngagementCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    portfolio = db.get(models.CommunityPortfolio, portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    engagement = community_service.record_engagement(
        db,
        portfolio,
        user_id=user.id,
        payload=payload,
    )
    db.commit()
    db.refresh(engagement)
    return engagement


@router.post(
    "/portfolios/{portfolio_id}/moderation",
    response_model=schemas.CommunityModerationEventOut,
)
async def moderate_portfolio(
    portfolio_id: UUID,
    payload: schemas.CommunityModerationDecision,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    portfolio = db.get(models.CommunityPortfolio, portfolio_id)
    if not portfolio:
        raise HTTPException(status_code=404, detail="Portfolio not found")
    if not user.is_admin and portfolio.created_by_id != user.id:
        raise HTTPException(status_code=403, detail="Moderation restricted")
    event = community_service.create_moderation_event(
        db,
        portfolio,
        actor_id=user.id,
        decision=payload,
    )
    db.commit()
    db.refresh(event)
    return event


@router.get("/feed", response_model=list[schemas.CommunityFeedEntry])
async def personalized_feed(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    entries = community_service.personal_feed(
        db,
        user_id=user.id,
        limit=limit,
    )
    return entries


@router.get("/trending", response_model=schemas.CommunityTrendingOut)
async def trending_feed(
    timeframe: str = Query("7d", pattern="^(24h|7d|30d)$"),
    limit: int = Query(10, ge=1, le=20),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return community_service.trending(
        db,
        timeframe=timeframe,
        limit=limit,
    )
