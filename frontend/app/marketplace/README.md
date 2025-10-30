# Marketplace Dashboard

The marketplace dashboard exposes BioLabs bundles, subscription insights, and billing utilities.

- **Plan Catalog** – renders pricing plans returned by `GET /api/billing/plans`, including SLA metadata and feature highlights.
- **Organization Billing Overview** – administrators can select an organization, review subscription health, inspect usage telemetry, and draft invoices for a billing period.
- **Credit Ledger & Adjustments** – credit adjustments feed the ledger table in real time and mirror backend `/api/billing/credits/adjust` responses.
- **Partner Listings** – legacy listing workflows remain available for partner-to-partner service exchanges.

The page relies on hooks from `frontend/app/hooks/useMarketplace.ts` and compliance organization lookups to maintain RBAC-aware selections.
