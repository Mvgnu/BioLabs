# Role-Sequenced Approval Orchestration Design

## Purpose
- Document the staged approval workflow required to replace the current single-signature export approvals.
- Provide implementation-ready specifications for backend models, API contracts, worker hooks, frontend experience, and testing scope.
- Align data, API, and UX decisions with compliance, auditability, and automation objectives.

## Context Snapshot
- `ExecutionNarrativeExport` stores a single approval status, approver, signature, and timestamps.
- Experiment console routes trigger export creation and approval updates without stage awareness.
- Frontend UI presents a single approve/reject control lacking SLA visibility or delegation flows.
- Packaging worker progresses artifacts once approval status switches to `approved`.

## Data Model Extensions
### Entities
| Table | Description | Key Fields |
| --- | --- | --- |
| `execution_narrative_approval_stages` | Ordered ladder describing required approvals for an export. | `id`, `export_id`, `stage_order`, `required_role`, `sla_hours`, `status`, `assignee_id`, `delegated_to_id`, `due_at`, `started_at`, `completed_at`, `rejected_at`, `notes`, `meta` |
| `execution_narrative_approval_actions` | Audit log of user actions against a stage. | `id`, `stage_id`, `action_type` (`requested`, `delegated`, `approved`, `rejected`, `reopened`, `escalated`, `overdue_flagged`), `actor_id`, `delegate_id`, `notes`, `payload`, `created_at` |

### Relationships & Constraints
- Each export owns an ordered collection of stages (`stage_order` unique per export).
- Only one stage may be active at a time; enforce via `status` enum (`pending`, `active`, `approved`, `rejected`, `skipped`).
- Actions cascade delete with their parent stage.
- `ExecutionNarrativeExport` gains:
  - `workflow_template_id: UUID | None`
  - `current_stage_id: UUID | None`
  - `approval_overdue: bool` (quick SLA breach flag)
  - `approval_started_at: datetime | None`
  - `approval_completed_at: datetime | None`

### Alembic Migration Checklist
1. Create `execution_narrative_approval_stages` and `execution_narrative_approval_actions` tables with UUID PKs, foreign keys to exports and stages, and indexes on `(export_id, stage_order)` and `(stage_id, created_at)`.
2. Add columns to `execution_narrative_exports` and backfill existing rows with a single stage representing the legacy approval (order 1, required role inferred from previous approver, status derived from `approval_status`).
3. Populate migration data script to move `approved_by_id`, `approved_at`, `approval_signature`, and `notes` into the seed stage/action records while preserving original columns for backward compatibility during rollout.
4. Set `approval_status` to be derived (`approved`, `pending`, `rejected`) from stage aggregate until follow-up cleanup removes redundant columns.

## Pydantic Schema Updates
- Introduce `ExecutionNarrativeApprovalStage` model with fields mirroring SQLAlchemy stage entity plus `actions: list[ExecutionNarrativeApprovalAction]` and computed flags (`is_active`, `is_overdue`).
- Extend `ExecutionNarrativeExport` schema to expose `workflow_template_id`, `current_stage`, `stages`, `approval_overdue`, and derived `approval_progress_percent`.
- Add request models:
  - `ExecutionNarrativeWorkflowInit` accepting `workflow_template_id` or explicit `stages: list[StageDefinition]` (role, sla_hours, optional user assignment).
  - `ExecutionNarrativeStageActionRequest` with `action` enum (`approve`, `reject`, `delegate`, `reassign`, `reset`) plus context fields (`delegate_id`, `notes`).

## API Contract Drafts
### Initialization
- **Route:** `POST /api/experiments/{execution_id}/exports`
- **Request:** existing export payload + optional `workflow_template_id` or `stages` definition.
- **Behavior:** if stages provided/template resolved, seed stage rows, mark first stage `active`, emit `narrative_export.approval.stage_started`.

### Stage Actions
- **Route:** `POST /api/exports/{export_id}/stages/{stage_id}/actions`
- **Auth:** ensure requester matches stage `assignee`, `delegated_to`, or holds `required_role`.
- **Validations:** prevent action on non-active stages, enforce rejection reasons, detect overdue states.
- **Responses:** updated export with refreshed stages and timeline events `stage_completed`, `stage_rejected`, `stage_delegated`.

### Delegation & Escalation
- **Route:** `POST /api/exports/{export_id}/stages/{stage_id}/delegate`
- **Payload:** `delegate_id`, optional `reason`.
- **Effects:** update `delegated_to_id`, append action log, adjust due date if delegation SLA differs, emit `stage_delegated`.

### Remediation Reset
- **Route:** `POST /api/exports/{export_id}/workflow/reset`
- **Payload:** `target_stage_order`, `reason`.
- **Outcome:** reopen stage, mark subsequent stages `pending`, create `stage_reopened` action.

### SLA Tracking Endpoint
- **Route:** `GET /api/exports/{export_id}/workflow`
- **Purpose:** return stage ladder, overdue flags, aggregated SLA metrics for UI polling.

## Worker & Scheduler Hooks
- Add Celery beat task `scan_overdue_approval_stages` to check stages where `status='active'` and `due_at < now`.
- Publish notifications and append `overdue_flagged` actions, toggling export-level `approval_overdue`.
- Integrate packaging worker guard so exports cannot enter artifact processing until `approval_completed_at` present and all stages `approved`.

## Frontend Experience
- Replace existing approval component with ladder visualization featuring:
  - Stage cards summarizing role, assignee, delegate, due date, status, and notes.
  - Inline controls for approve/reject, delegation modals, and SLA countdown badge.
  - Timeline sidebar listing recent actions sourced from stage action history.
- Update React hooks to consume new workflow endpoints, manage optimistic updates, and surface overdue alerts.
- Ensure legacy exports (single-stage) render as a one-card ladder.

## Test Matrix
### Backend
- Workflow creation with template resolution and explicit stage lists.
- Approval happy path across multiple stages, verifying state transitions and events.
- Delegation and reassignment flows including authorization checks.
- Rejection loop resetting to prior stage and verifying audit trail entries.
- SLA breach detection from worker task and packaging guard behavior.

### Frontend
- Rendering ladders for single-stage vs multi-stage exports.
- Approve/reject interactions with mocked API responses.
- Delegation modal flows and overdue indicator rendering.
- Regression coverage ensuring legacy single approval UI parity.

### End-to-End
- Scenario: create export with three stages, delegate stage two, reject and remediate, complete approvals, confirm packaging worker kicks in only after ladder finishes.

## Open Questions & Follow-Ups
- Should workflow templates be reusable entities or embedded JSON configs? (Lean toward templates table in follow-up iteration.)
- Determine notification channels (email, in-app) triggered by overdue detections.
- Plan migration cleanup removing legacy approval columns after clients fully adopt staged responses.
