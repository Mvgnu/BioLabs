# Multi-Step Cloning Planner Scope

- purpose: define the backend and frontend orchestration blueprint that chains existing sequence utilities into inventory-aware cloning plans
- status: draft
- updated: 2025-07-15
- related_docs: docs/governance/export_enforcement_audit.md, docs/governance/analytics_extension_plan.md

## Existing Building Blocks
- Sequence endpoints already expose primer design, restriction maps, GenBank parsing, chromatogram ingestion, and async analysis jobs via `/api/sequence/*` routes, backed by helpers in `backend/app/sequence.py` and FastAPI router `backend/app/routes/sequence.py`.【F:backend/app/routes/sequence.py†L13-L122】【F:backend/app/sequence.py†L1-L119】
- Inventory models and CSV exporter live in `backend/app/routes/inventory.py`, with items persisted through `models.InventoryItem`. Custody integration now surfaces `/api/inventory/samples` and `/api/inventory/items/{id}/custody` dashboards, linking planner sessions and DNA assets back to sample guardrail state.【F:backend/app/routes/inventory.py†L200-L347】
- Celery infrastructure exists for narrative packaging and sequence analysis jobs (`backend/app/tasks.py`, `backend/app/workers/packaging.py`), providing patterns for resumable orchestration and storage management.【F:backend/app/workers/packaging.py†L30-L221】【F:backend/app/tasks.py†L46-L69】
- Frontend sequence utilities sit under `frontend/app/sequence/` with hooks in `frontend/app/hooks` for API calls, which we can extend for planner flows.
- Sequence toolkit catalogs now include enzyme kinetics (`backend/app/data/enzyme_kinetics.json`) and ligation efficiency presets (`backend/app/data/ligation_profiles.json`) surfaced through cached loaders so planner stages can consume consistent parameters without re-reading disk.
- Guardrail snapshots inherit primer metadata tags, buffer provenance, and kinetics identifiers from these toolkit outputs so planner sessions and DNA asset serializers remain aligned.

## Backend Planner Orchestrator
1. **Session Model**: Introduce `CloningPlannerSession` ORM model capturing uploaded sequences, chosen assembly strategy (`gibson`, `golden_gate`, etc.), reagent selections, and Celery task handles. Leverage SQLAlchemy patterns from `models.SequenceAnalysisJob` for async lifecycle management.
2. **Workflow Engine**: Implement service layer `backend/app/services/cloning_planner.py` chaining:
   - Primer design (`design_primers`) with multiplex options.
   - Restriction analysis (`restriction_map`) filtered by assembly strategy.
   - Enzyme compatibility scoring and recommended digestion plans.
   - Assembly simulation (Gibson overlap checks, Golden Gate overhang validation).
   - Toolkit recommendation bundle builder merging preset scorecards, buffer guidance, and QC readiness for planner and DNA viewer consumers.
   - Payload contract builder stamping metadata tags for governance-aware dashboards.
   - Optional chromatogram QC ingestion to gate progression when sequencing data is attached.
3. **Inventory Awareness**: Query `models.InventoryItem` for enzyme/reagent SKUs, enforce reservations, and record expirations. Provide failure reasons when stock insufficient.
4. **Guardrail Hooks**: On finalization, trigger governance checks (restricted enzymes, policy compliance) using guardrail simulations before generating exportable assembly briefs, now enriched with primer metadata tags, ligation presets, buffer provenance, and kinetics identifiers for downstream DNA asset serialization.
5. **Persistence**: Store each stage output as JSON columns (e.g., `primer_set`, `restriction_digest`, `assembly_plan`) plus audit timestamps for resumable sessions.
6. **Celery Tasks**: Add chained Celery signatures per stage so intake → primers → restriction → assembly → QC → finalize checkpoints persist retries, task IDs, and guardrail summaries. Resume logic should restart from `current_step`, while cancellations revoke active tasks and freeze the checkpoint timeline.

## API Surface
- New router `backend/app/routes/cloning_planner.py` with endpoints:
  - `POST /api/cloning-planner/sessions` – create session, upload sequences, choose strategy.
  - `POST /api/cloning-planner/{session_id}/steps/{step}` – trigger stage transitions (primer, restriction, assembly, qc).
  - `POST /api/cloning-planner/{session_id}/resume` – restart orchestration from the persisted checkpoint with optional overrides.
  - `POST /api/cloning-planner/{session_id}/cancel` – revoke outstanding tasks, capture operator reason, and freeze the timeline for review.
  - `GET /api/cloning-planner/{session_id}` – retrieve aggregated outputs and guardrail status.
- `POST /api/cloning-planner/{session_id}/finalize` – persist final plan, enforce guardrails, attach inventory reservations.
- Schema updates in `backend/app/schemas.py` for session payloads and stage outputs.
- Real-time events stream (`GET /api/cloning-planner/{session_id}/events`) now exposes branch-aware payloads including guardrail gate transitions, checkpoint metadata, and timeline cursors so UI clients can replay halted sessions and custody escalations without polling. Each envelope also carries a `recovery_bundle` that pairs resume tokens, branch lineage deltas, mitigation hints, and guardrail readiness signals for deterministic restart flows, plus `drill_summaries` detailing custody drill overlays (severity, open escalation counts, resume readiness) derived from governance event overlays.
- Toolkit catalog route `GET /api/sequence-toolkit/presets` publishes curated preset metadata for planner intake and DNA viewer overlays, driving consistent preset selection experiences across surfaces.
- SSE envelopes additionally carry `recovery_context` metadata summarizing active holds, pending mitigation drills, and last resume timestamps so the frontend can render custody recovery actions alongside guardrail transitions.

## Timeline Replay & Branch Recovery
- Persist branch metadata (`active_branch_id`, `branch_state`) on each session alongside checkpoint payloads for every stage record, ensuring resume flows understand whether operators followed the mainline or a remediation branch.
- Emit SSE payloads with explicit `guardrail_transition` fields capturing prior and current gate states, plus `checkpoint` descriptors keyed by stage, enabling deterministic replay and governance auditing.
- Frontend `PlannerTimeline` component consumes the enriched stream, providing a scrubber that highlights guardrail holds, custody escalations, branch comparisons, mitigation hint links, and per-checkpoint resume controls so operators can narrate and restart recovery actions directly within the planner UI.
- Branch comparison envelopes now describe ahead checkpoints, missing reference stages, and divergent guardrail states, allowing operators to reconcile remediation branches before resuming halted work.
- Custody overlays include aggregated severity metrics, open drill/escalation totals, and resume-readiness deltas for the active and reference branches so replay operators immediately understand which branch carries higher governance risk before performing a resume action.
- `recovery_context` snapshots annotate stage history with guardrail hold lifecycle details (hold start, released timestamps, pending mitigations) and drive automatic Celery re-queues when custody recovery clears the gate, ensuring deterministic replay includes recovery provenance. Stage records now persist a `recovery_bundle` mirror of the SSE payload so downstream UIs can display resume readiness, open escalations, pending drills, and curated `drill_summaries` directly from history without recomputing guardrail state.

## Frontend Experience
- Create planner UI under `frontend/app/cloning-planner/` with multi-step wizard components (sequence upload, strategy selection, reagent confirmation, assembly preview).
- Extend `frontend/app/hooks` with `useCloningPlannerSession` hooking into new API endpoints.
- Reuse existing `frontend/app/sequence` visualization components for sequence previews; augment with stage status indicators and guardrail alerts.

## Testing Strategy
- Backend pytest suite covering:
  - Stage progression logic with mocked inventory/reservations.
  - Guardrail enforcement on restricted enzymes.
  - Celery task resume scenarios (failures, retries).
- Frontend Vitest coverage for wizard state transitions and API error handling.
- Contract tests verifying JSON schema for planner session payloads.

## Open Questions & Risks
- Need decision on enzyme metadata source (manual catalog vs. external DB).
- Inventory reservations may require locking semantics; consider reuse of existing booking/reservation systems in `backend/app/routes/schedule.py` for patterns.
- Chromatogram QC integration requires aligning file storage pipeline with planner session attachments.

## Documentation & SOP Hooks
- Update backend and frontend READMEs with planner module references once implemented.
- Draft assembly playbooks describing supported workflows, expected inputs, and operator escalation paths.
