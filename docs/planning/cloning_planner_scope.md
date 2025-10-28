# Multi-Step Cloning Planner Scope

- purpose: define the backend and frontend orchestration blueprint that chains existing sequence utilities into inventory-aware cloning plans
- status: draft
- updated: 2025-07-05
- related_docs: docs/governance/export_enforcement_audit.md, docs/governance/analytics_extension_plan.md

## Existing Building Blocks
- Sequence endpoints already expose primer design, restriction maps, GenBank parsing, chromatogram ingestion, and async analysis jobs via `/api/sequence/*` routes, backed by helpers in `backend/app/sequence.py` and FastAPI router `backend/app/routes/sequence.py`.【F:backend/app/routes/sequence.py†L13-L122】【F:backend/app/sequence.py†L1-L119】
- Inventory models and CSV exporter live in `backend/app/routes/inventory.py`, with items persisted through `models.InventoryItem`. Guardrail integration is pending (see audit document).【F:backend/app/routes/inventory.py†L193-L236】
- Celery infrastructure exists for narrative packaging and sequence analysis jobs (`backend/app/tasks.py`, `backend/app/workers/packaging.py`), providing patterns for resumable orchestration and storage management.【F:backend/app/workers/packaging.py†L30-L221】【F:backend/app/tasks.py†L46-L69】
- Frontend sequence utilities sit under `frontend/app/sequence/` with hooks in `frontend/app/hooks` for API calls, which we can extend for planner flows.
- Sequence toolkit catalogs now include enzyme kinetics (`backend/app/data/enzyme_kinetics.json`) and ligation efficiency presets (`backend/app/data/ligation_profiles.json`) surfaced through cached loaders so planner stages can consume consistent parameters without re-reading disk.

## Backend Planner Orchestrator
1. **Session Model**: Introduce `CloningPlannerSession` ORM model capturing uploaded sequences, chosen assembly strategy (`gibson`, `golden_gate`, etc.), reagent selections, and Celery task handles. Leverage SQLAlchemy patterns from `models.SequenceAnalysisJob` for async lifecycle management.
2. **Workflow Engine**: Implement service layer `backend/app/services/cloning_planner.py` chaining:
   - Primer design (`design_primers`) with multiplex options.
   - Restriction analysis (`restriction_map`) filtered by assembly strategy.
   - Enzyme compatibility scoring and recommended digestion plans.
   - Assembly simulation (Gibson overlap checks, Golden Gate overhang validation).
   - Payload contract builder stamping metadata tags for governance-aware dashboards.
   - Optional chromatogram QC ingestion to gate progression when sequencing data is attached.
3. **Inventory Awareness**: Query `models.InventoryItem` for enzyme/reagent SKUs, enforce reservations, and record expirations. Provide failure reasons when stock insufficient.
4. **Guardrail Hooks**: On finalization, trigger governance checks (restricted enzymes, policy compliance) using guardrail simulations before generating exportable assembly briefs.
5. **Persistence**: Store each stage output as JSON columns (e.g., `primer_set`, `restriction_digest`, `assembly_plan`) plus audit timestamps for resumable sessions.
6. **Celery Tasks**: Add `enqueue_cloning_plan` tasks to process heavy computations asynchronously, mirroring `enqueue_analyze_sequence_job` usage.

## API Surface
- New router `backend/app/routes/cloning_planner.py` with endpoints:
  - `POST /api/cloning-planner/sessions` – create session, upload sequences, choose strategy.
  - `POST /api/cloning-planner/{session_id}/steps/{step}` – trigger stage transitions (primer, restriction, assembly, qc).
  - `GET /api/cloning-planner/{session_id}` – retrieve aggregated outputs and guardrail status.
  - `POST /api/cloning-planner/{session_id}/finalize` – persist final plan, enforce guardrails, attach inventory reservations.
- Schema updates in `backend/app/schemas.py` for session payloads and stage outputs.

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
