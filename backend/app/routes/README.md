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
