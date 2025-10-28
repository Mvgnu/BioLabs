# Narrative Export Enforcement Audit

- purpose: catalogue every currently implemented narrative export initiation surface and record governance enforcement coverage
- status: draft
- updated: 2025-07-09
- related_docs: docs/approval_workflow_design.md, docs/narrative_lifecycle_overview.md

## Overview
The compliance stack now persists approval ladders, guardrail simulations, and packaging history, yet several export entry points still bypass the shared enforcement contract. This audit enumerates every discovered initiation surface and highlights whether `approval_ladders.record_packaging_queue_state` or equivalent blockers execute before an export artifact leaves the system.

## Request & API Surfaces
| Surface | File / Function | Guardrail State | Notes |
| --- | --- | --- | --- |
| Experiment Console export creation | `backend/app/routes/experiment_console.py:create_execution_narrative_export` | ✅ Uses `approval_ladders.initialise_export_ladder` and defers packaging until `record_packaging_queue_state` returns `True`. | Shared service confirms stage completion, logs awaiting events, and the worker reinspects state before artifact generation.【F:backend/app/routes/experiment_console.py†L3473-L3689】【F:backend/app/services/approval_ladders.py†L194-L284】 |
| Governance approvals | `backend/app/routes/experiment_console.py:approve_execution_narrative_export` | ✅ Calls `approval_ladders.record_stage_decision`, which returns `StageActionResult` and signals packaging readiness only after the final stage approves.【F:backend/app/routes/experiment_console.py†L4045-L4169】【F:backend/app/services/approval_ladders.py†L332-L457】 |
| Governance delegation/reset | `backend/app/routes/experiment_console.py` delegation/reset handlers | ✅ Mutate ladder state through service helpers that preserve stage gating semantics.【F:backend/app/routes/experiment_console.py†L4189-L4275】【F:backend/app/services/approval_ladders.py†L459-L552】 |
| Notebook PDF export | `backend/app/routes/notebook.py:export_entry` | ✅ Deprecated endpoint now records `notebook_export.guardrail_blocked` and returns `409 Conflict`, directing operators to the narrative packaging flow.【F:backend/app/routes/notebook.py†L104-L144】 |
| Inventory CSV export | `backend/app/routes/inventory.py:export_items` | ✅ Endpoint now returns `409 Conflict` with guidance to use governance-approved asset packaging instead of streaming raw CSV.【F:backend/app/routes/inventory.py†L194-L214】 |
| Experiment console artifact download | `backend/app/routes/experiment_console.py:download_execution_narrative_export_artifact` | ✅ Loads export via ladder-aware service before streaming, ensuring artifact existed only after approval。【F:backend/app/routes/experiment_console.py†L4275-L4356】【F:backend/app/services/approval_ladders.py†L131-L189】 |

## Background Tasks & Workers
| Surface | File / Function | Guardrail State | Notes |
| --- | --- | --- | --- |
| Celery packaging worker | `backend/app/workers/packaging.py:package_execution_narrative_export` | ✅ Reloads export with ladder, invokes `verify_export_packaging_guardrails`, and now relies on deduplicated queue telemetry so repeated pending runs stop spamming the timeline. Guardrail state is revalidated before any artifact writes.【F:backend/app/workers/packaging.py†L30-L221】【F:backend/app/services/approval_ladders.py†L233-L356】 |
| Packaging queue enqueue | `backend/app/services/approval_ladders.py:record_packaging_queue_state` | ✅ Central entry point for gating Celery dispatch; logs minimal `state/context` payloads (`guardrail_blocked`, `awaiting_approval`, `queued`) and persists the last emission in `export.meta` to prevent redundant events. Integration tests cover queue vs. block paths.【F:backend/app/services/approval_ladders.py†L233-L356】【F:backend/app/tests/governance/test_packaging_guardrails.py†L1-L156】 |
| SLA monitor escalation | `backend/app/tasks.py:monitor_narrative_approval_slas` | ✅ Marks overdue stages, emits escalation events, and now re-calls `verify_export_packaging_guardrails` which respects the deduplicated telemetry contract before notifying reviewers.【F:backend/app/tasks.py†L94-L205】【F:backend/app/services/approval_ladders.py†L233-L356】 |

## CLI & Operator Tools
| Surface | File / Function | Guardrail State | Notes |
| --- | --- | --- | --- |
| `queue-narrative-export` CLI | `backend/app/cli/migrate_templates.py:queue_narrative_export_command` | ✅ Routes through `dispatch_export_for_packaging_by_id`, returns guardrail summaries, and now participates in the shared telemetry contract so dashboards and operators receive consistent queue state payloads.【F:backend/app/cli/migrate_templates.py†L152-L243】【F:backend/app/services/approval_ladders.py†L233-L356】 |
| `migrate-exports` CLI | `backend/app/cli/migrate_templates.py:migrate_exports_command` | ⚠️ Read/modify only. Adjusts metadata but does not dispatch packaging; continue to run a follow-up queue check via the command above before approving migrations.【F:backend/app/cli/migrate_templates.py†L1-L117】 |

## Outstanding Actions
1. Continue auditing future export additions to ensure they reuse `dispatch_export_for_packaging[_by_id]` or land with a deprecation path plus guardrail telemetry.
2. Extend CLI regression coverage to include dry-run vs. commit migration scenarios once follow-on enforcement hooks are prioritised.
3. Maintain the operator SOP (`docs/governance/operator_sop.md`) alongside future enforcement changes so dashboard guidance stays accurate.

## Test Coverage Snapshot
- `backend/app/tests/test_experiment_console.py::test_narrative_export_packaging_blocked_until_final_stage` asserts API-to-worker blocking semantics and event emission.【F:backend/app/tests/test_experiment_console.py†L736-L848】
- `backend/app/tests/governance/test_export_surface_guardrails.py` verifies notebook and inventory exports are blocked without governance packaging.【F:backend/app/tests/governance/test_export_surface_guardrails.py†L1-L86】

## Guardrail Telemetry Contract

All packaging telemetry now flows through a sanitiser that enforces the minimal payload specification below before events reach the execution log. The helper is shared by API dispatch, CLI utilities, Celery workers, and SLA monitors so consumers see identical shapes regardless of the initiating surface.

| Event | Required Fields | Optional Context Keys |
| --- | --- | --- |
| `narrative_export.packaging.guardrail_blocked` | `export_id`, `state` | `guardrail_state`, `projected_delay_minutes`, `reasons` |
| `narrative_export.packaging.awaiting_approval` | `export_id`, `state` | `pending_stage_id`, `pending_stage_index`, `pending_stage_status`, `pending_stage_due_at` |
| `narrative_export.packaging.queued` | `export_id`, `state` | `version` |
| `narrative_export.packaging.started` / `retrying` | `export_id`, `version`, `attempt` | — |
| `narrative_export.packaging.ready` | `export_id`, `version`, `artifact_file_id`, `checksum`, `attempt` | — |
| `narrative_export.packaging.failed` | `export_id`, `version`, `attempt`, `error` | — |

- Sanitisation occurs inside `services.approval_ladders.record_packaging_queue_state` and `workers.packaging.package_execution_narrative_export`, trimming any stray fields while preserving the queue metadata persisted to `export.meta["packaging_queue_state"]` for UI reuse.【F:backend/app/services/approval_ladders.py†L233-L356】【F:backend/app/workers/packaging.py†L200-L311】
- Governance pytest coverage asserts both the sanitiser behaviour and the guardrail enforcement paths for CLI and worker flows, ensuring parity with API-triggered checks.【F:backend/app/tests/governance/test_packaging_guardrails.py†L1-L212】【F:backend/app/tests/test_cli_narrative_exports.py†L1-L122】

