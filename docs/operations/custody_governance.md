# Custody Governance Playbook

## Overview
The custody governance service provides end-to-end oversight for DNA asset storage, freezer utilization, and custody lineage. It layers guardrail heuristics on top of freezer topology metadata so governance operators can reason about occupancy risks, stale custody records, and missing provenance links.

## Data Model
- **`governance_freezer_units`** — describes individual freezer appliances, their facility metadata, and guardrail configuration knobs. Units can be globally shared or assigned to a specific team.
- **`governance_freezer_compartments`** — captures hierarchical freezer topology (shelves, racks, boxes) with optional capacity constraints and escalation thresholds.
- **`governance_sample_custody_logs`** — records each custody movement, linking DNA asset versions and cloning planner sessions to freezer compartments, quantity deltas, and guardrail flags.

## Guardrail Heuristics
- Capacity ceilings are enforced by either the compartment `capacity` column or `guardrail_thresholds.max_capacity`. Hitting either limit emits a `capacity.exceeded` flag.
- Minimum inventory guardrails (`guardrail_thresholds.min_capacity`) trigger `capacity.depleted` when occupancy falls below the configured floor.
- Utilization warnings compare total occupancy with `guardrail_thresholds.critical_utilization` to surface early congestion.
- Custody entries without DNA asset lineage (missing asset version and planner session references) emit a `lineage.unlinked` flag.
- Compartment lookup failures record a `compartment.missing` flag to highlight topology drift.

## API Surfaces
- `GET /api/governance/custody/freezers` returns freezer units with nested compartments, occupancy counts, and guardrail summaries for dashboard overlays.
- `GET /api/governance/custody/logs` exposes custody history filtered by DNA asset, planner session, or compartment identifiers to support audits and investigations.
- `POST /api/governance/custody/logs` persists guardrail-evaluated custody actions, automatically stamping provenance metadata and generating escalation cues.

## Standard Operating Procedure
1. Governance operators model freezer units and compartments via Alembic migrations or admin tooling, ensuring guardrail thresholds mirror facility SOPs.
2. Custody events are recorded immediately after physical transfers; the API autocomputes occupancy deltas and guardrail flags.
3. Dashboards poll the freezer topology endpoint to visualize occupancy heatmaps, highlight compartments nearing capacity, and identify lineage gaps requiring remediation.
4. Escalation workflows reference `guardrail_flags` within custody logs to launch investigations, update planner sessions, or trigger remediation tasks.

## Documentation Expectations
- Service-level details live in `backend/app/services/sample_governance.py` with structured metadata tags.
- API coverage is summarized in `backend/app/routes/sample_governance.py` and the routes README.
- Future governance features should update this document with new guardrail types, delegated RBAC roles, or SOP adjustments.
