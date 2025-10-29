# Routes Module Overview

## Experiment Console Orchestrator
- **File**: `experiment_console.py`
- **New capabilities**:
  - `blocked_reason`, `required_actions`, and `auto_triggers` fields are appended to each `ExperimentStepStatus` response to capture orchestration decisions.
  - `_prepare_step_gate_context` aggregates inventory, booking, equipment maintenance, and approval signals for step gating.
  - `_evaluate_step_gate` and `_store_step_progress` centralize rule checks and persistence for both manual and automated updates.
  - `POST /api/experiment-console/sessions/{execution_id}/steps/{step_index}/advance` attempts to move a step forward after running gating checks and returns actionable blockers when transitions are denied.
  - `_apply_remediation_actions` provides transactional execution of resource locks, approvals, and follow-up scheduling, updating `execution.result` with `locks`, `followups`, and `remediation_log` metadata.
  - `POST /api/experiment-console/sessions/{execution_id}/steps/{step_index}/remediate` applies orchestrator-selected actions (auto-triggers or explicit requests) and responds with both the refreshed session payload and per-action outcomes.
  - `POST /api/experiment-console/sessions/{execution_id}/exports/narrative` hydrates attachments across notebook, analytics, QC, and remediation domains while persisting hydration context for the packaging worker.
  - `GET /api/experiment-console/governance/timeline/stream` delivers SSE frames with reversal lock lifecycle updates and cooldown ticks so the experiment console can render real-time governance context without refetching paginated timelines.
  - `GET /api/experiments/{execution_id}/scenarios` returns the scientist scenario workspace bundle (execution summary, available snapshots, and saved scenarios) with RBAC enforcement.
  - `POST /api/experiments/{execution_id}/scenarios` persists a new preview scenario, while `PUT`, `POST .../clone`, and `DELETE` endpoints enable scenario lifecycle management with execution timeline events.
- **Resource recovery actions**: action strings follow the `domain:verb:identifier` convention and map to remediation helpers on the console UI (e.g., `inventory:restore:<id>`).
- **Compliance data**: orchestration inspects execution parameters for `step_requirements` and `required_approvals`; granted approvals should be stored under `execution.result["compliance"]["approvals"]` when external systems clear a gate.

## Frontend Coordination
- The console UI (see `frontend/app/experiment-console/[executionId]/page.tsx`) renders blocker banners, remediation CTAs, and suggested automations based on the orchestration fields returned by the backend.
- Automated CTAs invoke the dedicated remediation endpoint first and fall back to legacy APIs (`/api/inventory/items/{id}`, `/api/equipment/maintenance`) only when orchestration reports unsupported actions.

> Evidence discovery endpoints:
> - `GET /api/notebook/entries/evidence` surfaces notebook entry descriptors for attachment pickers.
> - `GET /api/data/evidence` provides analytics snapshot, QC metric, and remediation report descriptors with cursor pagination and execution filters.

> These notes must be kept current when additional gating signals or orchestration endpoints are introduced.

## Governance Coaching Notes
- **Module**: `governance_notes/__init__.py`
- **Capabilities**:
  - `GET /api/governance/overrides/{override_id}/coaching-notes` streams threaded coaching history with reply counts and actor summaries.
  - `POST /api/governance/overrides/{override_id}/coaching-notes` persists inline notes or threaded replies with automatic root tracking.
  - `PATCH /api/governance/coaching-notes/{note_id}` updates bodies, moderation states, and metadata with edit timestamping.
- **RBAC**: Access gated via override actor roles, execution ownership, or team membership derived from baseline/template lineage.
- **Metadata**: Responses expose `metadata`, `moderation_state`, and `reply_count` fields for optimistic UI updates.

## DNA Assets Lifecycle
- **Module**: `dna_assets.py`
- **Capabilities**:
- `POST /api/dna-assets` seeds DNA assets with initial sequence payloads, tags, and annotations.
- `POST /api/dna-assets/{asset_id}/versions` appends versions while updating guardrail-ready summaries.
- `GET /api/dna-assets/{asset_id}/diff` emits structured diff metrics (substitutions, insertions, deletions, GC delta) for viewer overlays.
- `GET /api/dna-assets/{asset_id}/viewer` composes viewer-ready payloads containing feature tracks, guardrail summaries, translations, kinetics, and optional diffs against a comparison version.
- `POST /api/dna-assets/{asset_id}/guardrails` records governance events tied to asset versions for dashboard telemetry.
- **RBAC**: Restricted to asset creators and administrators during the initial implementation phase; team-scoped filters will expand in follow-up work.

## Custody Governance
- **Module**: `sample_governance.py`
- **Capabilities**:
  - `GET /api/governance/custody/freezers` emits freezer unit topology trees with compartment occupancy, latest activity, and guardrail alerts.
- `GET /api/governance/custody/logs` surfaces custody ledger entries filtered by asset, planner session, protocol execution, execution event, or compartment for audit timelines.
  - `POST /api/governance/custody/logs` records guardrail-evaluated custody movements, automatically flagging lineage or capacity concerns.
- `GET /api/governance/custody/escalations` exposes SLA-tracked escalation queue entries with severity, due times, guardrail metadata, and protocol execution context for operators.
- `GET /api/governance/custody/protocols` streams guardrail snapshots for protocol executions, including escalation overlays, drill counts, QC backpressure, and supports filtering by status, severity, drill state, team, template, or execution identifiers.
  - `POST /api/governance/custody/escalations/{id}/acknowledge|notify|resolve` manages escalation lifecycle actions, dispatching notifications and stamping audit timestamps.
  - `GET /api/governance/custody/faults` lists freezer incident telemetry, while `POST /api/governance/custody/freezers/{freezer_id}/faults` and `/faults/{fault_id}/resolve` enable manual incident capture and closure.
- **RBAC**: Limited to administrators while custody guardrail policies stabilize; team-scoped queries enforce membership checks when filtering by team identifiers.
