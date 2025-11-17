# Marketplace Billing & Monetization

## Overview
The billing surface pairs marketplace bundles with organization-level subscriptions, usage telemetry, and credit ledgers. Pricing plans expose base pricing, SLA tiers, feature matrices, and credit allowances that downstream services consume when emitting monetized events.

## Key Concepts
- **Pricing Plans** (`marketplace_pricing_plans`): define bundle metadata, billing cadence, base fees, and allowed credits. Plans include structured feature descriptors for storefront rendering and automation.
- **Subscriptions** (`marketplace_subscriptions`): bind organizations to plans, track SLA acceptance payloads, and manage current credit balances. Subscriptions own invoice and ledger history.
- **Usage Events** (`marketplace_usage_events`): capture guardrail-aware consumption for planner, instrumentation, analytics, or other services. Events debit credits and annotate guardrail flags for compliance analytics.
- **Invoices** (`marketplace_invoices`): aggregate base fees with overage charges into draft or issued invoices, enabling exports to financial tooling.
- **Credit Ledger** (`marketplace_credit_ledger`): provides a chronological record of debits and grants, including manual adjustments and usage-derived movements.

## API Highlights
- `GET /api/billing/plans` returns storefront-ready plans. When the catalog is empty, a default "Lab Standard" plan is bootstrapped for sandbox environments.
- `POST /api/billing/organizations/{organization_id}/subscriptions` provisions a subscription and allocates initial credits.
- `POST /api/billing/usage` records monetized usage with guardrail annotations. Planner finalization, instrumentation runs, and sequence analysis jobs emit events automatically.
- `POST /api/billing/subscriptions/{subscription_id}/invoices/draft` materializes draft invoices across a billing period. Additional endpoints list invoices, adjust credits, and surface credit ledgers for finance teams.

## Guardrail Integration
Usage emissions reuse existing guardrail payloads: planner finalization embeds open escalation codes, instrumentation runs capture guardrail flags, and analytics workloads note unit quantities. Credit adjustments and invoice generation respect organization residency and RBAC constraints inherited from compliance services.

## Frontend Experience
The marketplace storefront (see `frontend/app/marketplace/page.tsx`) renders plan cards, subscription health, usage history, invoices, and credit ledger timelines. Administrators can draft invoices, top up credits, and manage partner listings from a single dashboard.
