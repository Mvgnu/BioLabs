"""Marketplace billing and credit orchestration services."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas

# purpose: orchestrate monetization pricing, subscriptions, and credit ledgers
# status: experimental
# depends_on: backend.app.models.MarketplacePricingPlan, backend.app.models.MarketplaceSubscription
# related_docs: docs/marketplace/billing.md


class BillingError(RuntimeError):
    """Base error for monetization flows."""


class PricingPlanNotFound(BillingError):
    """Raised when a requested pricing plan cannot be located."""


class SubscriptionNotFound(BillingError):
    """Raised when a subscription is required but unavailable."""


def list_pricing_plans(db: Session) -> list[models.MarketplacePricingPlan]:
    """Return pricing plans with features for storefront rendering."""

    plans: Sequence[models.MarketplacePricingPlan] = (
        db.query(models.MarketplacePricingPlan)
        .options(joinedload(models.MarketplacePricingPlan.features))
        .order_by(models.MarketplacePricingPlan.base_price_cents.asc())
        .all()
    )
    if not plans:
        plans = _bootstrap_default_plans(db)
        db.commit()
    return list(plans)


def create_subscription(
    db: Session,
    organization_id: UUID,
    payload: schemas.MarketplaceSubscriptionCreate,
) -> models.MarketplaceSubscription:
    """Provision an organization subscription bound to a pricing plan."""

    plan = db.get(models.MarketplacePricingPlan, payload.plan_id)
    if not plan:
        raise PricingPlanNotFound(f"plan {payload.plan_id} not found")

    existing = (
        db.query(models.MarketplaceSubscription)
        .filter(
            models.MarketplaceSubscription.organization_id == organization_id,
            models.MarketplaceSubscription.plan_id == payload.plan_id,
            models.MarketplaceSubscription.status == "active",
        )
        .one_or_none()
    )
    if existing:
        return existing

    now = datetime.now(timezone.utc)
    renews_at = _compute_default_renewal(now, plan.billing_cadence)
    subscription = models.MarketplaceSubscription(
        organization_id=organization_id,
        plan_id=plan.id,
        status="active",
        billing_email=payload.billing_email,
        started_at=now,
        renews_at=renews_at,
        sla_acceptance=payload.sla_acceptance,
        current_credits=plan.credit_allowance,
        subscription_metadata={"plan_slug": plan.slug},
        created_at=now,
        updated_at=now,
    )
    db.add(subscription)
    db.flush()
    db.refresh(subscription)
    if plan.credit_allowance:
        _append_credit_ledger(
            db,
            subscription,
            delta=plan.credit_allowance,
            reason="initial_allocation",
            metadata={"plan_slug": plan.slug},
        )
    return subscription


def record_usage_event(
    db: Session,
    payload: schemas.MarketplaceUsageEventCreate,
) -> models.MarketplaceUsageEvent:
    """Persist a monetized usage event and update credit balances."""

    subscription = _resolve_subscription(db, payload.organization_id, payload.subscription_id)
    if not subscription:
        raise SubscriptionNotFound("active subscription required for usage event")

    occurred_at = payload.occurred_at or datetime.now(timezone.utc)
    event = models.MarketplaceUsageEvent(
        subscription_id=subscription.id,
        organization_id=payload.organization_id,
        team_id=payload.team_id,
        user_id=payload.user_id,
        service=payload.service,
        operation=payload.operation,
        unit_quantity=payload.unit_quantity,
        credits_consumed=payload.credits_consumed,
        guardrail_flags=payload.guardrail_flags,
        event_metadata=payload.metadata,
        occurred_at=occurred_at,
        created_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.flush()
    db.refresh(event)

    if payload.credits_consumed:
        new_balance = subscription.current_credits - payload.credits_consumed
        subscription.current_credits = new_balance
        subscription.updated_at = datetime.now(timezone.utc)
        _append_credit_ledger(
            db,
            subscription,
            delta=-payload.credits_consumed,
            reason=f"usage:{payload.service}:{payload.operation}",
            usage_event=event,
            metadata={"unit_quantity": payload.unit_quantity},
        )
    return event


def apply_credit_adjustment(
    db: Session,
    payload: schemas.MarketplaceCreditAdjustmentCreate,
) -> models.MarketplaceCreditLedger:
    """Apply a manual credit adjustment to a subscription."""

    subscription = db.get(models.MarketplaceSubscription, payload.subscription_id)
    if not subscription or subscription.status != "active":
        raise SubscriptionNotFound("active subscription required for adjustment")

    subscription.current_credits += payload.delta_credits
    subscription.updated_at = datetime.now(timezone.utc)
    entry = _append_credit_ledger(
        db,
        subscription,
        delta=payload.delta_credits,
        reason=f"adjustment:{payload.reason}",
        metadata=payload.metadata,
    )
    return entry


def list_usage_events(
    db: Session,
    organization_id: UUID,
    *,
    limit: int = 100,
) -> list[models.MarketplaceUsageEvent]:
    """Return latest usage events for an organization."""

    events = (
        db.query(models.MarketplaceUsageEvent)
        .filter(models.MarketplaceUsageEvent.organization_id == organization_id)
        .order_by(models.MarketplaceUsageEvent.occurred_at.desc())
        .limit(limit)
        .all()
    )
    return list(events)


def list_invoices(
    db: Session,
    subscription_id: UUID,
) -> list[models.MarketplaceInvoice]:
    """Return invoices linked to a subscription."""

    invoices = (
        db.query(models.MarketplaceInvoice)
        .filter(models.MarketplaceInvoice.subscription_id == subscription_id)
        .order_by(models.MarketplaceInvoice.period_start.desc())
        .all()
    )
    return list(invoices)


def get_active_subscription(
    db: Session,
    organization_id: UUID,
) -> models.MarketplaceSubscription | None:
    """Return the most recent active subscription for an organization."""

    return (
        db.query(models.MarketplaceSubscription)
        .options(
            joinedload(models.MarketplaceSubscription.plan).joinedload(
                models.MarketplacePricingPlan.features
            ),
        )
        .filter(models.MarketplaceSubscription.organization_id == organization_id)
        .filter(models.MarketplaceSubscription.status == "active")
        .order_by(models.MarketplaceSubscription.started_at.desc())
        .first()
    )


def list_credit_ledger(
    db: Session,
    subscription_id: UUID,
    *,
    limit: int = 100,
) -> list[models.MarketplaceCreditLedger]:
    """Return recent credit ledger movements for a subscription."""

    entries = (
        db.query(models.MarketplaceCreditLedger)
        .filter(models.MarketplaceCreditLedger.subscription_id == subscription_id)
        .order_by(models.MarketplaceCreditLedger.created_at.desc())
        .limit(limit)
        .all()
    )
    return list(entries)


def draft_invoice_from_events(
    db: Session,
    subscription_id: UUID,
    *,
    period_start: datetime,
    period_end: datetime,
) -> models.MarketplaceInvoice:
    """Create a draft invoice capturing usage within a period."""

    subscription = db.get(models.MarketplaceSubscription, subscription_id)
    if not subscription:
        raise SubscriptionNotFound(f"subscription {subscription_id} not found")

    usage_rows: Iterable[models.MarketplaceUsageEvent] = (
        db.query(models.MarketplaceUsageEvent)
        .filter(models.MarketplaceUsageEvent.subscription_id == subscription_id)
        .filter(models.MarketplaceUsageEvent.occurred_at >= period_start)
        .filter(models.MarketplaceUsageEvent.occurred_at < period_end)
        .all()
    )

    credit_usage = sum(row.credits_consumed for row in usage_rows)
    amount_due = subscription.plan.base_price_cents
    line_items = [
        {
            "type": "base_fee",
            "description": f"{subscription.plan.title} ({subscription.plan.billing_cadence})",
            "amount_cents": subscription.plan.base_price_cents,
        }
    ]
    if credit_usage > subscription.plan.credit_allowance:
        overage = credit_usage - subscription.plan.credit_allowance
        overage_rate = subscription.plan.plan_metadata.get("overage_rate_cents", 0)
        overage_amount = overage * overage_rate
        amount_due += overage_amount
        line_items.append(
            {
                "type": "overage",
                "description": f"Credit overage ({overage} units)",
                "amount_cents": overage_amount,
            }
        )

    invoice = models.MarketplaceInvoice(
        subscription_id=subscription.id,
        organization_id=subscription.organization_id,
        invoice_number=_generate_invoice_number(subscription),
        period_start=period_start,
        period_end=period_end,
        amount_due_cents=amount_due,
        credit_usage=credit_usage,
        status="draft",
        line_items=line_items,
        created_at=datetime.now(timezone.utc),
    )
    db.add(invoice)
    db.flush()
    db.refresh(invoice)
    return invoice


def _resolve_subscription(
    db: Session,
    organization_id: UUID,
    subscription_id: UUID | None,
) -> models.MarketplaceSubscription | None:
    if subscription_id:
        subscription = db.get(models.MarketplaceSubscription, subscription_id)
        if subscription and subscription.organization_id == organization_id:
            return subscription
        return None

    return (
        db.query(models.MarketplaceSubscription)
        .filter(models.MarketplaceSubscription.organization_id == organization_id)
        .filter(models.MarketplaceSubscription.status == "active")
        .order_by(models.MarketplaceSubscription.started_at.desc())
        .first()
    )


def _append_credit_ledger(
    db: Session,
    subscription: models.MarketplaceSubscription,
    *,
    delta: int,
    reason: str,
    usage_event: models.MarketplaceUsageEvent | None = None,
    metadata: dict[str, object] | None = None,
) -> models.MarketplaceCreditLedger:
    metadata = metadata or {}
    entry = models.MarketplaceCreditLedger(
        subscription_id=subscription.id,
        organization_id=subscription.organization_id,
        usage_event_id=usage_event.id if usage_event else None,
        delta_credits=delta,
        reason=reason,
        running_balance=subscription.current_credits,
        ledger_metadata=metadata,
        created_at=datetime.now(timezone.utc),
    )
    db.add(entry)
    db.flush()
    db.refresh(entry)
    if usage_event:
        usage_event.ledger_entry = entry
    return entry


def _compute_default_renewal(start: datetime, cadence: str) -> datetime:
    if cadence == "annual":
        return start + timedelta(days=365)
    if cadence == "quarterly":
        return start + timedelta(days=90)
    return start + timedelta(days=30)


def _generate_invoice_number(subscription: models.MarketplaceSubscription) -> str:
    now = datetime.now(timezone.utc)
    return f"{subscription.organization_id.hex[:6]}-{subscription.plan.slug}-{now.strftime('%Y%m%d%H%M%S')}"


def _bootstrap_default_plans(db: Session) -> list[models.MarketplacePricingPlan]:
    """Install a default pricing plan to simplify sandbox environments."""

    now = datetime.now(timezone.utc)
    plan = models.MarketplacePricingPlan(
        slug="lab-standard",
        title="Lab Standard",
        description="Core cloning planner, instrumentation, and analytics bundle",
        billing_cadence="monthly",
        base_price_cents=12000,
        credit_allowance=500,
        sla_tier="standard",
        plan_metadata={"overage_rate_cents": 25},
        created_at=now,
        updated_at=now,
    )
    plan.features = [
        models.MarketplacePlanFeature(
            feature_key="planner.finalize",
            label="Cloning planner finalization",
            details="Finalize and export planner sessions with guardrail provenance",
            created_at=now,
        ),
        models.MarketplacePlanFeature(
            feature_key="instrumentation.dispatch",
            label="Robotic instrumentation dispatch",
            details="Reserve, dispatch, and monitor digital twins with SLA-backed telemetry",
            created_at=now,
        ),
        models.MarketplacePlanFeature(
            feature_key="analytics.sequence",
            label="Sequence analytics credits",
            details="Run sequence analysis and anomaly detection workloads",
            created_at=now,
        ),
    ]
    db.add(plan)
    db.flush()
    db.refresh(plan)
    return [plan]
