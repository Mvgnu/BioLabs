# Governance Export Operator SOP

- purpose: Provide a step-by-step playbook for operators enforcing narrative export guardrails across API, worker, scheduler, CLI, and UI surfaces.
- status: pilot
- updated: 2025-07-11
- related_docs: docs/governance/export_enforcement_audit.md, docs/governance/analytics_extension_plan.md, docs/governance/preview.md

## 1. Enforcement Surfaces

### 1.1 API Dispatch
- All narrative export creations (`POST /api/experiment-console/sessions/{execution_id}/exports/narrative`) initialise approval ladders and defer packaging until `services.approval_ladders.record_packaging_queue_state` allows dispatch. Pass `?dry_run=true` to audit guardrail readiness without enqueuing workers.
- Subsequent approval, delegation, and reset APIs reuse `services.approval_ladders.dispatch_export_for_packaging`, which now calls `verify_export_packaging_guardrails` to block side effects when stages reopen. Approval endpoints also accept `?dry_run=true` when you need a parity check that records telemetry but stops before Celery dispatch.
- Legacy notebook (`GET /api/notebook/entries/{entry_id}/export`) and inventory (`GET /api/inventory/export`) endpoints are formally deprecated. They emit guardrail block events and respond with `409 Conflict`, redirecting operators to narrative or DNA asset packaging workflows.

### 1.2 Celery Workers
- `workers/packaging.py:package_execution_narrative_export` re-loads the export on every execution and invokes `verify_export_packaging_guardrails`. Pending ladders trigger a single `narrative_export.packaging.awaiting_approval` event with a sanitised payload; repeated attempts reuse the persisted `packaging_queue_state` metadata instead of duplicating telemetry.
- `tasks.py:monitor_narrative_approval_slas` escalates overdue stages and now reissues `verify_export_packaging_guardrails` to ensure guardrail telemetry stays synchronized before notifications while respecting the deduplicated payloads.

### 1.3 CLI Utilities
- `python -m backend.app.cli queue-narrative-export <export-id>` routes through `dispatch_export_for_packaging_by_id`, surfaces guardrail status, pending stage information, and guardrail forecasts, and now emits the same sanitised telemetry payloads consumed by dashboards and workers. Pass `--dry-run` to mirror guardrail checks without dispatching Celery jobs; use this before manual retries to confirm enforcement parity.

### 1.4 Scheduler Jobs
- Celery beat schedules call `monitor_narrative_approval_slas` every 15 minutes. When stage SLAs breach, the task logs `stage_overdue` and `stage_escalated` events, revalidates guardrails, and invalidates analytics caches.

### 1.5 UI Dashboards
- The guardrail health dashboard (`/governance/dashboard`) now leads with a queue summary that reuses the sanitised packaging payloads emitted by API, CLI, workers, and SLA monitors. Operators should resolve any `Guardrail blocked` entries before attempting retries.
- Review thresholds, alert routing, and dry-run verification steps in `docs/governance/guardrail_health_runbook.md` before acknowledging alerts surfaced by the dashboard.
- The overdue dashboard (`/governance/dashboard`) visualises overdue volumes, role pressure, and export-level guardrails. It consumes the analytics meta payload populated by the tasks above and exposes mailto escalation affordances tied to the SOP.
- Inventory CSV downloads are no longer surfaced in UI due to guardrail deprecation; dashboards should link to approved asset dossiers instead.

## 2. Escalation Procedure

1. Open `/governance/dashboard` and clear any `Guardrail blocked` queue entries surfaced by the guardrail health cards before progressing to overdue escalations.
2. Review the "Overdue stage queue" table and role pressure map for stages breaching SLA tolerance (mean open minutes > 60).
3. Click the **Escalate** action beside a stage to email `governance-ops@biolabs.local` with a pre-filled subject referencing the export identifier. Attach context from the dashboard (role, detected timestamp) and the guardrail forecast surfaced in CLI or API payloads.
4. Document the escalation outcome in the execution timeline via the experiment console or governance workspace.
5. After remediation, re-run `python -m backend.app.cli queue-narrative-export <export-id>` to confirm `queued` is `True`. The CLI mirrors the guardrail checks used by workers.

## 3. Verification Checklist

- [ ] Confirm `verify_export_packaging_guardrails` blocks packaging when any stage returns to `in_progress`.
- [ ] Use API (`?dry_run=true`) and CLI (`--dry-run`) probes to confirm guardrail readiness before issuing manual retries.
- [ ] Ensure `monitor_narrative_approval_slas` records `narrative_export.packaging.awaiting_approval` alongside escalation events and that `packaging_queue_state.context` mirrors pending stage metadata after sanitisation.
- [ ] Confirm notebook and inventory export attempts log guardrail block events and produce `409 Conflict` responses.
- [ ] Validate `/governance/dashboard` reflects the latest guardrail queue states and overdue counts after cache invalidation (max 30s delay).
- [ ] Update Problem Trackers under `/problems/` if enforcement inconsistencies persist across two monitoring cycles.

## 4. References

- `backend/app/services/approval_ladders.py` – shared guardrail helpers (`record_packaging_queue_state`, `verify_export_packaging_guardrails`).
- `backend/app/workers/packaging.py` – Celery worker guarding packaging side effects.
- `backend/app/tasks.py` – SLA monitor integrating guardrail revalidation.
- `frontend/app/components/governance/GuardrailHealthDashboard.tsx` – guardrail queue dashboard consuming sanitised packaging payloads.
- `frontend/app/components/governance/OverdueDashboard.tsx` – dashboard implementation consuming analytics meta.
