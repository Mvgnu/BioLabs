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
- **Resource recovery actions**: action strings follow the `domain:verb:identifier` convention and map to remediation helpers on the console UI (e.g., `inventory:restore:<id>`).
- **Compliance data**: orchestration inspects execution parameters for `step_requirements` and `required_approvals`; granted approvals should be stored under `execution.result["compliance"]["approvals"]` when external systems clear a gate.

## Frontend Coordination
- The console UI (see `frontend/app/experiment-console/[executionId]/page.tsx`) renders blocker banners, remediation CTAs, and suggested automations based on the orchestration fields returned by the backend.
- Automated CTAs invoke the dedicated remediation endpoint first and fall back to legacy APIs (`/api/inventory/items/{id}`, `/api/equipment/maintenance`) only when orchestration reports unsupported actions.

> These notes must be kept current when additional gating signals or orchestration endpoints are introduced.
