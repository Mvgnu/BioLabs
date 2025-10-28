# Documentation Readiness Checklist

- purpose: enumerate README, SOP, and runbook touchpoints that must be updated alongside upcoming governance, planner, and DNA asset work
- status: draft
- updated: 2025-07-05
- related_docs: docs/governance/export_enforcement_audit.md, docs/planning/cloning_planner_scope.md, docs/planning/dna_asset_model_draft.md

## Governance Hardening
- `backend/app/README.md` – add section covering cross-surface ladder enforcement, notebook/inventory export blockers, and CLI safeguards.【F:backend/app/README.md†L1-L200】
- `backend/app/routes/README.md` – document new guardrail decorators for export endpoints once implemented.
- `docs/governance/baselines.md` & `docs/governance/timeline.md` – insert references to overdue-stage analytics dashboard and enforcement audit findings.【F:docs/governance/baselines.md†L1-L160】【F:docs/governance/timeline.md†L1-L200】
- New SOP under `docs/governance/` describing operator workflows for approving exports via CLI, API, and worker tooling.

## Cloning Planner Launch
- `backend/app/services/README.md` – add planner service entry referencing orchestration helpers.【F:backend/app/services/README.md†L1-L160】
- `backend/app/analytics/README.md` – mention planner metrics feeding governance dashboards once implemented.【F:backend/app/analytics/README.md†L1-L160】
- `frontend/README.md` & `frontend/app/sequence/README.md` (create if missing) – outline planner wizard, hooks, and visualization tie-ins.【F:frontend/README.md†L1-L200】
- `docs/planning/README.md` – mark checklist items as delivered when planner ships.【F:docs/planning/README.md†L1-L120】
- New assembly playbook under `docs/` (e.g., `docs/assembly_workflows.md`) capturing supported strategies, QC prerequisites, and guardrails.

## DNA Asset Management
- `backend/app/README.md` – extend architecture section with DNA asset APIs and storage namespaces.
- `backend/app/workers/README.md` – describe background tasks for checksum verification & archival.【F:backend/app/workers/README.md†L1-L160】
- `frontend/app/components/governance/README.md` – cover asset approval widgets tied to guardrails.【F:frontend/app/components/governance/README.md†L1-L200】
- New viewer guide under `docs/` (e.g., `docs/dna_asset_viewer.md`) explaining circular/linear viewers and diff overlays.
- `progress.md` – log milestones when data model and viewers land.【F:progress.md†L1-L80】
- `docs/reflections/` – add reflection entries capturing lessons from governance integration after asset rollout.

## Sample Governance & Sharing Hub (Forward Look)
- `backend/app/routes/governance_notes/README.md` – update with freezer governance APIs once modeled.【F:backend/app/routes/governance_notes/README.md†L1-L160】
- `frontend/app/governance/README.md` – document dashboards for ladder health, sharing reviews, and freezer alerts.
- New collaboration SOP referencing guardrail-aware merge/fork flows for DNA/protocol assets.

## Tracking & Automation
- Initiate a persistent `docs/problem-tracker/README.md` to consolidate structured tracker usage for recurring guardrail issues.
- Embed `purpose:`/`status:` metadata blocks in new source files (services, routers, Celery tasks) to maintain machine-readable documentation per project standards.
