# Samples Dashboard

## purpose
Provide a custody-aware dashboard for governed laboratory samples, combining inventory state, guardrail escalations, and linked planner or DNA asset references.

## status
pilot

## components
- `components/SampleDashboard.tsx`: renders the summary table and detail panels
- `page.tsx`: Next.js entry point that mounts the dashboard view

## data dependencies
- `/api/inventory/samples` for summary metadata
- `/api/inventory/items/{id}/custody` for detailed custody ledger and escalation data

## related_docs
- `docs/operations/custody_governance.md`
- `docs/planning/cloning_planner_scope.md`
