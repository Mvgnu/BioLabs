# DNA Asset Data Model Draft

- purpose: specify the relational schema and service layer requirements for construct/plasmid asset management with visualization support
- status: draft
- updated: 2025-07-05
- related_docs: docs/planning/cloning_planner_scope.md, docs/governance/export_enforcement_audit.md

## Design Goals
- Persist plasmids/constructs with version history, checksum validation, and guardrail-aware governance states.
- Support ingestion of GenBank/SBOL/SnapGene files and capture original metadata for provenance.
- Provide diffable annotations powering frontend circular/linear viewers and collaboration workflows.

## Proposed Tables
1. **dna_assets**
   - `id UUID PK`
   - `name` (string, required)
   - `description` (text)
   - `slug` (unique)
   - `project_id` (FK to `projects.id`, optional)
   - `team_id` (FK to `teams.id`, optional)
   - `created_by` / `updated_by` (FK to `users.id`)
   - `governance_state` (`draft`, `restricted`, `approved`, etc.)
   - `created_at`, `updated_at`
   - `current_version_id` (FK to `dna_asset_versions.id`)
2. **dna_asset_versions**
   - `id UUID PK`
   - `asset_id` (FK to `dna_assets.id`)
   - `version_index` (int, auto-increment per asset)
   - `source_format` (`genbank`, `sbol`, `snapgene`, `fasta`)
  - `sequence_length`, `gc_content`
   - `checksum_sha256`
   - `storage_path` (path in object storage; reuse storage helpers from narrative packaging `backend/app/workers/packaging.py`).【F:backend/app/workers/packaging.py†L148-L210】
   - `imported_at`, `imported_by`
   - `notes JSON`
3. **dna_asset_annotations**
   - `id UUID PK`
   - `version_id` (FK)
   - `feature_type`
   - `start_bp`, `end_bp`, `strand`
   - `qualifiers JSONB`
   - `source_id` (original identifier from file)
4. **dna_asset_tags**
   - `asset_id`, `tag` (composite PK) to support quick filtering and governance restrictions (e.g., `restricted_enzyme`, `human_dna`).
5. **dna_asset_attachments**
   - Link to chromatograms, QC reports, assembly plans (FK to `files.id`, `cloning_planner_sessions.id` once implemented).
6. **dna_asset_governance_events**
   - Audit table recording guardrail results, approvals, overrides (similar to `ExecutionNarrativeApprovalStage` events) for historical traceability.【F:backend/app/services/approval_ladders.py†L213-L457】

## API & Service Layer
- Create `backend/app/services/dna_assets.py` with helpers for import, diff, version promotion, and guardrail checks.
- Add FastAPI router `backend/app/routes/dna_assets.py` exposing CRUD + version history endpoints, diff endpoints (`GET /assets/{id}/versions/{a}/diff/{b}`), and governance transitions.
- Extend `backend/app/schemas.py` with Pydantic models for assets, versions, annotations, diffs, and governance actions.

## Migration Plan
1. Generate Alembic revision creating new tables with indexes:
   - Unique constraint on `(asset_id, version_index)`.
   - GIN index on `dna_asset_annotations.qualifiers` for metadata search.
   - Partial index on `dna_assets(governance_state)` for quick restricted queries.
2. Backfill script to import existing protocol template sequences (if any) as seed assets.
3. Wire storage namespace `dna-assets/{asset_id}/v{version}` for binary files, reusing `save_binary_payload` & checksum verification utilities.【F:backend/app/storage.py†L44-L110】

## Visualization Hooks
- Provide API endpoints returning linear & circular viewer configs (features grouped by type, color hints) to drive forthcoming `frontend/app/components/dna` components.
- Diff endpoint returns aligned sequences plus annotation delta lists for UI overlays.

## Governance Integration
- When governance state transitions to `restricted`, enqueue guardrail simulation similar to narrative exports (`approval_ladders.attach_guardrail_forecast`) to predict enforcement impact.【F:backend/app/services/approval_ladders.py†L131-L205】
- Require approval ladder completion for publishing restricted constructs; reuse `approval_ladders` service or design specialized DNA ladder variant.

## Testing Outline
- Pytest covering imports from GenBank/SBOL fixtures verifying annotations persist.
- Diff tests ensuring checksum changes tracked and annotation comparisons accurate.
- Governance tests verifying restricted constructs block downloads until approvals finalize.

## Documentation Checklist
- Update backend README with DNA asset APIs and storage notes.
- Produce DNA asset viewer usage guide alongside SOP describing governance workflows.
- Add entries to progress log and reflections once implemented.
