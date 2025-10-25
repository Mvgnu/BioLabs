# Routes Module Overview

## Experiment Console Orchestrator
- **File**: `experiment_console.py`
- **New capabilities**:
  - `blocked_reason`, `required_actions`, and `auto_triggers` fields are appended to each `ExperimentStepStatus` response to capture orchestration decisions.
  - `_prepare_step_gate_context` aggregates inventory, booking, equipment maintenance, and approval signals for step gating.
  - `_evaluate_step_gate` and `_store_step_progress` centralize rule checks and persistence for both manual and automated updates.
  - `POST /api/experiment-console/sessions/{execution_id}/steps/{step_index}/advance` attempts to move a step forward after running gating checks and returns actionable blockers when transitions are denied.
- **Resource recovery actions**: action strings follow the `domain:verb:identifier` convention and map to remediation helpers on the console UI (e.g., `inventory:restore:<id>`).
- **Compliance data**: orchestration inspects execution parameters for `step_requirements` and `required_approvals`; granted approvals should be stored under `execution.result["compliance"]["approvals"]` when external systems clear a gate.

## Frontend Coordination
- The console UI (see `frontend/app/experiment-console/[executionId]/page.tsx`) renders blocker banners, remediation CTAs, and suggested automations based on the orchestration fields returned by the backend.
- Automated CTAs invoke existing APIs (`/api/inventory/items/{id}`, `/api/equipment/maintenance`) where possible and refresh the execution session on success.

> These notes must be kept current when additional gating signals or orchestration endpoints are introduced.
