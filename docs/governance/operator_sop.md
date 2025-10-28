# Governance Export Operator SOP

- purpose: Provide a step-by-step playbook for operators enforcing narrative export guardrails across API, worker, scheduler, CLI, and UI surfaces.
- status: pilot
- updated: 2025-07-07
- related_docs: docs/governance/export_enforcement_audit.md, docs/governance/analytics_extension_plan.md, docs/governance/preview.md

## 1. Enforcement Surfaces

### 1.1 API Dispatch
- All narrative export creations (`POST /api/experiment-console/sessions/{execution_id}/exports/narrative`) initialise approval ladders and defer packaging until `services.approval_ladders.record_packaging_queue_state` allows dispatch.
- Subsequent approval, delegation, and reset APIs reuse `services.approval_ladders.dispatch_export_for_packaging`, which now calls `verify_export_packaging_guardrails` to block side effects when stages reopen.
- Operators reviewing exports through `/api/governance/exports/*` inherit the same enforcement contract.

### 1.2 Celery Workers
- `workers/packaging.py:package_execution_narrative_export` re-loads the export on every execution and invokes `verify_export_packaging_guardrails`. Pending ladders trigger a single `narrative_export.packaging.awaiting_approval` event with a compact `state` payload; repeated attempts reuse the persisted `packaging_queue_state` metadata instead of duplicating telemetry.
- `tasks.py:monitor_narrative_approval_slas` escalates overdue stages and now reissues `verify_export_packaging_guardrails` to ensure guardrail telemetry stays synchronized before notifications while respecting the deduplicated payloads.

### 1.3 CLI Utilities
- `python -m backend.app.cli queue-narrative-export <export-id>` routes through `dispatch_export_for_packaging_by_id` and surfaces guardrail status, pending stage information, and guardrail forecasts. Use this command before manually retrying packaging jobs.

### 1.4 Scheduler Jobs
- Celery beat schedules call `monitor_narrative_approval_slas` every 15 minutes. When stage SLAs breach, the task logs `stage_overdue` and `stage_escalated` events, revalidates guardrails, and invalidates analytics caches.

### 1.5 UI Dashboards
- The governance overdue dashboard (`/governance/dashboard`) visualises overdue volumes, role pressure, and export-level guardrails. It consumes the analytics meta payload populated by the tasks above and exposes mailto escalation affordances tied to the SOP.

## 2. Escalation Procedure

1. Open `/governance/dashboard` to review the "Overdue stage queue" table and role pressure map.
2. Prioritise stages with `Active breaches` or mean open minutes exceeding 60 minutes.
3. Click the **Escalate** action beside a stage to email `governance-ops@biolabs.local` with a pre-filled subject referencing the export identifier. Attach context from the dashboard (role, detected timestamp) and the guardrail forecast surfaced in CLI or API payloads.
4. Document the escalation outcome in the execution timeline via the experiment console or governance workspace.
5. After remediation, re-run `python -m backend.app.cli queue-narrative-export <export-id>` to confirm `queued` is `True`. The CLI mirrors the guardrail checks used by workers.

## 3. Verification Checklist

- [ ] Confirm `verify_export_packaging_guardrails` blocks packaging when any stage returns to `in_progress`.
- [ ] Ensure `monitor_narrative_approval_slas` records `narrative_export.packaging.awaiting_approval` alongside escalation events.
- [ ] Validate `/governance/dashboard` reflects the latest overdue counts after cache invalidation (max 30s delay).
- [ ] Update Problem Trackers under `/problems/` if enforcement inconsistencies persist across two monitoring cycles.

## 4. References

- `backend/app/services/approval_ladders.py` – shared guardrail helpers (`record_packaging_queue_state`, `verify_export_packaging_guardrails`).
- `backend/app/workers/packaging.py` – Celery worker guarding packaging side effects.
- `backend/app/tasks.py` – SLA monitor integrating guardrail revalidation.
- `frontend/app/components/governance/OverdueDashboard.tsx` – dashboard implementation consuming analytics meta.
