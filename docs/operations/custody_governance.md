# Custody Governance Playbook

## Overview
The custody governance service provides end-to-end oversight for DNA asset storage, freezer utilization, and custody lineage. It layers guardrail heuristics on top of freezer topology metadata so governance operators can reason about occupancy risks, stale custody records, and missing provenance links.

## Data Model
- **`governance_freezer_units`** — describes individual freezer appliances, their facility metadata, and guardrail configuration knobs. Units can be globally shared or assigned to a specific team.
- **`governance_freezer_compartments`** — captures hierarchical freezer topology (shelves, racks, boxes) with optional capacity constraints and escalation thresholds.
- **`governance_sample_custody_logs`** — records each custody movement, linking DNA asset versions and cloning planner sessions to freezer compartments, quantity deltas, and guardrail flags.
- **`governance_custody_escalations`** — persists SLA-driven escalation queue entries with guardrail metadata, notification history, and RBAC ownership details for operators.
- **`governance_freezer_faults`** — captures freezer health incidents (temperature excursions, sensor faults, offline states) sourced from guardrail telemetry for mitigation drill tracking.

## Guardrail Heuristics
- Capacity ceilings are enforced by either the compartment `capacity` column or `guardrail_thresholds.max_capacity`. Hitting either limit emits a `capacity.exceeded` flag.
- Minimum inventory guardrails (`guardrail_thresholds.min_capacity`) trigger `capacity.depleted` when occupancy falls below the configured floor.
- Utilization warnings compare total occupancy with `guardrail_thresholds.critical_utilization` to surface early congestion.
- Custody entries without DNA asset lineage (missing asset version and planner session references) emit a `lineage.unlinked` flag.
- Compartment lookup failures record a `compartment.missing` flag to highlight topology drift.
- Escalation timers inherit freezer-level `guardrail_config.escalation` defaults and may be overridden per compartment via `guardrail_thresholds.escalation.{severity}_sla_minutes`. Breaches automatically enqueue `governance_custody_escalations` rows, dispatch governance notifications, and expose action controls in the custody dashboard.
- Guardrail metadata (e.g., `fault.temperature.high`) automatically records freezer faults with severity heuristics and lineage context so reliability teams can coordinate mitigation plays.

## API Surfaces
- `GET /api/governance/custody/freezers` returns freezer units with nested compartments, occupancy counts, and guardrail summaries for dashboard overlays.
- `GET /api/governance/custody/logs` exposes custody history filtered by DNA asset, planner session, or compartment identifiers to support audits and investigations.
- `POST /api/governance/custody/logs` persists guardrail-evaluated custody actions, automatically stamping provenance metadata and generating escalation cues.
- `GET /api/governance/custody/escalations` surfaces SLA-tracked escalation queue entries with severity, due times, and guardrail context for RBAC-hardened operators.
- `POST /api/governance/custody/escalations/{id}/acknowledge` assigns ownership to the acting operator while preserving audit timestamps.
- `POST /api/governance/custody/escalations/{id}/notify` retransmits escalation notifications (email + in-app) to freezer guardians when additional coordination is required.
- `POST /api/governance/custody/escalations/{id}/resolve` records mitigation completion and stamps resolution timestamps.
- `GET /api/governance/custody/faults` lists active and resolved freezer faults for dashboard overlays.
- `POST /api/governance/custody/freezers/{freezer_id}/faults` enables operations teams to log manual incidents tied to SOP drills.
- `POST /api/governance/custody/faults/{fault_id}/resolve` closes fault records once mitigation steps finish.

## Standard Operating Procedure
1. Governance operators model freezer units and compartments via Alembic migrations or admin tooling, ensuring guardrail thresholds mirror facility SOPs.
2. Custody events are recorded immediately after physical transfers; the API autocomputes occupancy deltas, guardrail flags, and—when necessary—spawns escalation entries alongside freezer faults.
3. Dashboards poll the freezer topology endpoint to visualize occupancy heatmaps, highlight compartments nearing capacity, and identify lineage gaps requiring remediation. The custody escalation panel aggregates SLA queues and freezer health incidents, enabling operators to acknowledge, notify, or resolve items without leaving the workspace.
4. Escalation workflows reference `guardrail_flags` within custody logs and the dedicated escalation endpoints to launch investigations, update planner sessions, or trigger remediation tasks. Operators should acknowledge escalations before coordinating via the `notify` endpoint and resolve records only after SOP mitigation steps conclude.

## Documentation Expectations
- Service-level details live in `backend/app/services/sample_governance.py` with structured metadata tags.
- API coverage is summarized in `backend/app/routes/sample_governance.py` and the routes README.
- Future governance features should update this document with new guardrail types, delegated RBAC roles, or SOP adjustments.
