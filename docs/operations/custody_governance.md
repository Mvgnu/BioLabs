# Custody Governance Playbook

## Overview
The custody governance service provides end-to-end oversight for DNA asset storage, freezer utilization, and custody lineage. It layers guardrail heuristics on top of freezer topology metadata so governance operators can reason about occupancy risks, stale custody records, and missing provenance links.

## Data Model
- **`governance_freezer_units`** — describes individual freezer appliances, their facility metadata, and guardrail configuration knobs. Units can be globally shared or assigned to a specific team.
- **`governance_freezer_compartments`** — captures hierarchical freezer topology (shelves, racks, boxes) with optional capacity constraints and escalation thresholds.
- **`governance_sample_custody_logs`** — records each custody movement, linking DNA asset versions, cloning planner sessions, and protocol execution checkpoints to freezer compartments, quantity deltas, and guardrail flags so provenance timelines remain intact across lab workflows.
- **`governance_custody_escalations`** — persists SLA-driven escalation queue entries with guardrail metadata, protocol execution references, notification history, and RBAC ownership details for operators.
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
- `GET /api/governance/custody/logs` exposes custody history filtered by DNA asset, planner session, protocol execution, execution events, or compartment identifiers to support audits and investigations.
- `POST /api/governance/custody/logs` persists guardrail-evaluated custody actions, automatically stamping provenance metadata and generating escalation cues.
- `GET /api/governance/custody/escalations` surfaces SLA-tracked escalation queue entries with severity, due times, guardrail context, and protocol execution metadata for RBAC-hardened operators. Filters allow operators to zero in on specific protocol runs or execution steps.
- `GET /api/governance/custody/protocols` streams protocol execution guardrail snapshots, including aggregated escalation counts, recovery drill status, mitigation checklists by execution event, and QC backpressure signals. Filters support guardrail status selection, drill gating, severity-specific triage, team membership scoping, template identifiers, and explicit execution targeting.
- `POST /api/governance/custody/escalations/{id}/acknowledge` assigns ownership to the acting operator while preserving audit timestamps.
- `POST /api/governance/custody/escalations/{id}/notify` retransmits escalation notifications (email + in-app) to freezer guardians when additional coordination is required.
- `POST /api/governance/custody/escalations/{id}/resolve` records mitigation completion and stamps resolution timestamps.
- `GET /api/governance/custody/faults` lists active and resolved freezer faults for dashboard overlays.
- `POST /api/governance/custody/freezers/{freezer_id}/faults` enables operations teams to log manual incidents tied to SOP drills.
- `POST /api/governance/custody/faults/{fault_id}/resolve` closes fault records once mitigation steps finish.

## Standard Operating Procedure
1. Governance operators model freezer units and compartments via Alembic migrations or admin tooling, ensuring guardrail thresholds mirror facility SOPs.
2. Custody events are recorded immediately after physical transfers; the API autocomputes occupancy deltas, guardrail flags, and—when necessary—spawns escalation entries alongside freezer faults. When protocol execution identifiers or step events are provided, the custody ledger embeds the reference so experiment narratives reflect custody provenance automatically.
3. Dashboards poll the freezer topology endpoint to visualize occupancy heatmaps, highlight compartments nearing capacity, and identify lineage gaps requiring remediation. The custody escalation panel aggregates SLA queues, freezer health incidents, and protocol execution context so operators can inspect linked SOP steps and mitigation checklists without leaving the workspace.
4. Escalation workflows reference `guardrail_flags` within custody logs and the dedicated escalation endpoints to launch investigations, update planner sessions, or trigger remediation tasks. Operators should acknowledge escalations before coordinating via the `notify` endpoint and resolve records only after SOP mitigation steps conclude. Escalations that breach SLA automatically mark a recovery drill in the escalation metadata and stamp the associated protocol execution record, ensuring governance dashboards highlight follow-up duties until the drill is closed. The protocol snapshot endpoint surfaces recovery gates (`guardrail_status` transitions from `halted` → `alert` → `monitor` → `stable`), QC backpressure toggles, and mitigation checklists grouped by execution event so operators can replay the drill timeline directly from the governance workspace.

## Protocol Execution Guardrail States
- `guardrail_status` captures the aggregate custody posture for each protocol execution. `halted` indicates active critical escalations (including acknowledged-but-unresolved events), `alert` denotes open warning escalations, `monitor` tracks informational guardrails, `stabilizing` persists after mitigations while residual history remains, and `stable` reflects a clean ledger.
- `guardrail_state` persists structured metadata (open escalation counts, open drill tallies, QC backpressure flags, and execution event overlays) so downstream dashboards can replay mitigation steps. Each overlay lists contributing escalation IDs and mitigation checklist items derived from guardrail flags, ensuring scientists and governance operators have synchronized SOP prompts during recovery drills.

## Documentation Expectations
- Service-level details live in `backend/app/services/sample_governance.py` with structured metadata tags.
- API coverage is summarized in `backend/app/routes/sample_governance.py` and the routes README.
- Future governance features should update this document with new guardrail types, delegated RBAC roles, or SOP adjustments.
