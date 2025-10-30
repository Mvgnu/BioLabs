"""Billing and monetization API surface."""

from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from ..services import billing

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/plans", response_model=List[schemas.MarketplacePricingPlanOut])
def list_pricing_plans(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> List[schemas.MarketplacePricingPlanOut]:
    plans = billing.list_pricing_plans(db)
    return [schemas.MarketplacePricingPlanOut.model_validate(plan) for plan in plans]


@router.post(
    "/organizations/{organization_id}/subscriptions",
    response_model=schemas.MarketplaceSubscriptionOut,
)
def create_subscription(
    organization_id: UUID,
    payload: schemas.MarketplaceSubscriptionCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not _user_can_manage_org(user, organization_id):
        raise HTTPException(status_code=403, detail="insufficient permissions")
    subscription = billing.create_subscription(db, organization_id, payload)
    db.commit()
    db.refresh(subscription)
    return schemas.MarketplaceSubscriptionOut.model_validate(subscription)


@router.get(
    "/organizations/{organization_id}/subscriptions",
    response_model=schemas.MarketplaceSubscriptionOut | None,
)
def get_subscription(
    organization_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not _user_can_manage_org(user, organization_id):
        raise HTTPException(status_code=403, detail="insufficient permissions")
    subscription = billing.get_active_subscription(db, organization_id)
    if not subscription:
        return None
    return schemas.MarketplaceSubscriptionOut.model_validate(subscription)


@router.get(
    "/organizations/{organization_id}/usage",
    response_model=List[schemas.MarketplaceUsageEventOut],
)
def list_usage(
    organization_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> List[schemas.MarketplaceUsageEventOut]:
    if not _user_can_manage_org(user, organization_id):
        raise HTTPException(status_code=403, detail="insufficient permissions")
    events = billing.list_usage_events(db, organization_id)
    return [schemas.MarketplaceUsageEventOut.model_validate(evt) for evt in events]


@router.post("/usage", response_model=schemas.MarketplaceUsageEventOut)
def create_usage_event(
    payload: schemas.MarketplaceUsageEventCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if not _user_can_manage_org(user, payload.organization_id):
        raise HTTPException(status_code=403, detail="insufficient permissions")
    event = billing.record_usage_event(db, payload)
    db.commit()
    db.refresh(event)
    return schemas.MarketplaceUsageEventOut.model_validate(event)


@router.post("/credits/adjust", response_model=schemas.MarketplaceCreditLedgerOut)
def adjust_credits(
    payload: schemas.MarketplaceCreditAdjustmentCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    subscription = db.get(models.MarketplaceSubscription, payload.subscription_id)
    if not subscription or not _user_can_manage_org(user, subscription.organization_id):
        raise HTTPException(status_code=403, detail="insufficient permissions")
    entry = billing.apply_credit_adjustment(db, payload)
    db.commit()
    db.refresh(entry)
    return schemas.MarketplaceCreditLedgerOut.model_validate(entry)


@router.get(
    "/subscriptions/{subscription_id}/invoices",
    response_model=List[schemas.MarketplaceInvoiceOut],
)
def subscription_invoices(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> List[schemas.MarketplaceInvoiceOut]:
    subscription = db.get(models.MarketplaceSubscription, subscription_id)
    if not subscription or not _user_can_manage_org(user, subscription.organization_id):
        raise HTTPException(status_code=403, detail="insufficient permissions")
    invoices = billing.list_invoices(db, subscription_id)
    return [schemas.MarketplaceInvoiceOut.model_validate(inv) for inv in invoices]


@router.post(
    "/subscriptions/{subscription_id}/invoices/draft",
    response_model=schemas.MarketplaceInvoiceOut,
)
def draft_subscription_invoice(
    subscription_id: UUID,
    payload: schemas.MarketplaceInvoiceDraftRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    subscription = db.get(models.MarketplaceSubscription, subscription_id)
    if not subscription or not _user_can_manage_org(user, subscription.organization_id):
        raise HTTPException(status_code=403, detail="insufficient permissions")
    invoice = billing.draft_invoice_from_events(
        db,
        subscription_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
    )
    db.commit()
    db.refresh(invoice)
    return schemas.MarketplaceInvoiceOut.model_validate(invoice)


@router.get(
    "/subscriptions/{subscription_id}/ledger",
    response_model=List[schemas.MarketplaceCreditLedgerOut],
)
def subscription_ledger(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
) -> List[schemas.MarketplaceCreditLedgerOut]:
    subscription = db.get(models.MarketplaceSubscription, subscription_id)
    if not subscription or not _user_can_manage_org(user, subscription.organization_id):
        raise HTTPException(status_code=403, detail="insufficient permissions")
    entries = billing.list_credit_ledger(db, subscription_id)
    return [schemas.MarketplaceCreditLedgerOut.model_validate(entry) for entry in entries]


def _user_can_manage_org(user, organization_id: UUID) -> bool:
    if getattr(user, "is_admin", False):
        return True
    org_ids = {
        member.team.organization_id
        for member in getattr(user, "teams", [])
        if member.team and member.team.organization_id
    }
    return organization_id in org_ids
