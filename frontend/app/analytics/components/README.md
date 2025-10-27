# Reviewer Cadence Primitives

- purpose: document reusable reviewer cadence visualisation components for governance analytics
- scope: lightweight display primitives (tables, alert lists) that render reviewer throughput metrics
- status: pilot

## Components

- `ReviewerCadenceTable.tsx` – renders a compact table of reviewer cadence metrics (load band, latency percentiles, churn signal).
- `ReviewerCadenceAlerts.tsx` – lists reviewers with active publish streak alerts using cadence payloads.

These components accept already-normalised governance payloads and deliberately avoid hard-coding layout containers so dashboards can compose them inside cards, modals, or inline callouts.
