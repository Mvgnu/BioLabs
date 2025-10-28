# Narrative Export Enforcement Audit

- purpose: catalogue every currently implemented narrative export initiation surface and record governance enforcement coverage
- status: draft
- updated: 2025-07-05
- related_docs: docs/approval_workflow_design.md, docs/narrative_lifecycle_overview.md

## Overview
The compliance stack now persists approval ladders, guardrail simulations, and packaging history, yet several export entry points still bypass the shared enforcement contract. This audit enumerates every discovered initiation surface and highlights whether `approval_ladders.record_packaging_queue_state` or equivalent blockers execute before an export artifact leaves the system.

## Request & API Surfaces
| Surface | File / Function | Guardrail State | Notes |
| --- | --- | --- | --- |
| Experiment Console export creation | `backend/app/routes/experiment_console.py:create_execution_narrative_export` | ✅ Uses `approval_ladders.initialise_export_ladder` and defers packaging until `record_packaging_queue_state` returns `True`. | Shared service confirms stage completion, logs awaiting events, and the worker reinspects state before artifact generation.【F:backend/app/routes/experiment_console.py†L3473-L3689】【F:backend/app/services/approval_ladders.py†L194-L284】 |
| Governance approvals | `backend/app/routes/experiment_console.py:approve_execution_narrative_export` | ✅ Calls `approval_ladders.record_stage_decision`, which returns `StageActionResult` and signals packaging readiness only after the final stage approves.【F:backend/app/routes/experiment_console.py†L4045-L4169】【F:backend/app/services/approval_ladders.py†L332-L457】 |
| Governance delegation/reset | `backend/app/routes/experiment_console.py` delegation/reset handlers | ✅ Mutate ladder state through service helpers that preserve stage gating semantics.【F:backend/app/routes/experiment_console.py†L4189-L4275】【F:backend/app/services/approval_ladders.py†L459-L552】 |
| Notebook PDF export | `backend/app/routes/notebook.py:export_entry` | ❌ Streams PDF immediately with no guardrail or approval hook. Needs ladder integration or explicit governance exemption policy.【F:backend/app/routes/notebook.py†L104-L149】 |
| Inventory CSV export | `backend/app/routes/inventory.py:export_items` | ❌ Direct CSV writer bypasses governance services. Requires guardrail simulation check, ladder configuration, and audit logging before streaming.【F:backend/app/routes/inventory.py†L193-L236】 |
| Experiment console artifact download | `backend/app/routes/experiment_console.py:download_execution_narrative_export_artifact` | ✅ Loads export via ladder-aware service before streaming, ensuring artifact existed only after approval。【F:backend/app/routes/experiment_console.py†L4275-L4356】【F:backend/app/services/approval_ladders.py†L131-L189】 |

## Background Tasks & Workers
| Surface | File / Function | Guardrail State | Notes |
| --- | --- | --- | --- |
| Celery packaging worker | `backend/app/workers/packaging.py:package_execution_narrative_export` | ✅ Reloads export with ladder, invokes `verify_export_packaging_guardrails`, and emits `awaiting_approval` events instead of packaging when approvals regress. Guardrail state is revalidated before any artifact writes.【F:backend/app/workers/packaging.py†L30-L221】【F:backend/app/services/approval_ladders.py†L308-L347】 |
| Packaging queue enqueue | `backend/app/services/approval_ladders.py:record_packaging_queue_state` | ✅ Central entry point for gating Celery dispatch; logs guardrail blocks and stage waits. Integration tests cover queue vs. block paths.【F:backend/app/services/approval_ladders.py†L213-L307】【F:backend/app/tests/test_experiment_console.py†L736-L848】 |
| SLA monitor escalation | `backend/app/tasks.py:monitor_narrative_approval_slas` | ✅ Marks overdue stages, emits escalation events, and now re-calls `verify_export_packaging_guardrails` to ensure telemetry stays in sync before notifying reviewers.【F:backend/app/tasks.py†L94-L205】【F:backend/app/services/approval_ladders.py†L308-L347】 |

## CLI & Operator Tools
| Surface | File / Function | Guardrail State | Notes |
| --- | --- | --- | --- |
| `migrate-exports` CLI | `backend/app/cli/migrate_templates.py:migrate_exports_command` | ⚠️ Read/modify only. Adjusts metadata but does not dispatch packaging; however, lacks confirmation that migrated exports remain blocked until ladders complete. Should invoke integrity checks post-migration.【F:backend/app/cli/migrate_templates.py†L1-L117】 |

## Outstanding Actions
1. Wrap notebook and inventory exports with ladder-aware workflows or explicitly mark them as governance-exempt with audit justification.
2. Introduce shared enforcement decorators for CLI utilities and any future scheduler tasks to ensure `record_packaging_queue_state` runs before artifact generation.
3. Expand integration coverage to include CLI dry-run vs. commit scenarios once enforcement hooks exist.
4. Maintain the operator SOP (`docs/governance/operator_sop.md`) alongside future enforcement changes so dashboard guidance stays accurate.

## Test Coverage Snapshot
- `backend/app/tests/test_experiment_console.py::test_narrative_export_packaging_blocked_until_final_stage` asserts API-to-worker blocking semantics and event emission.【F:backend/app/tests/test_experiment_console.py†L736-L848】
- No pytest cases currently assert guardrail behavior for notebook or inventory exports; add once enforcement is implemented.

