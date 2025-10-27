# Narrative Lifecycle Overview

## Current State Assessment
- Narrative exports now rely on the Celery-driven packaging worker (`backend/app/workers/packaging.py`), introducing retries, lifecycle events, and multi-domain evidence hydration spanning notebook entries, analytics snapshots, QC metrics, remediation reports, and files with contextual manifests.
- Storage helpers (`backend/app/storage.py`) provide signed URLs, checksum validation, and namespaced paths; downstream consumers still lack awareness of manifest digests and retention policies.
- Export schemas and models (`backend/app/models.py`, `backend/app/schemas.py`) track lifecycle timestamps, attempt counters, and manifest hashes, yet user interfaces and audit APIs have not been updated to expose the richer state.
- Experiment console routes (`backend/app/routes/experiment_console.py`) surface job queueing and monitoring, while evidence acquisition, approvals, and dossier previews continue to mirror the earlier minimal experiences.

## High-Impact Evolution Tracks

### 1. Expand Evidence Bundling Into a Multi-Domain Narrative Fabric
Broaden the export pipeline so narratives can embed notebooks, QC metrics, analytics, remediation summaries, and contextual lab assets rather than only timeline attachments.

**Key Actions**
1. Audit attachment models and serializers to catalog current fields and constraints.
2. Define new evidence enums and typed payload schemas for notebooks, analytics snapshots, QC metrics, and remediation reports with forward-compatible manifest digests.
3. Implement backend collection services that expose normalized evidence descriptors with pagination and filtering.
4. Extend the packaging worker to hydrate each evidence type, embedding rendered markdown, metric rollups, and remediation context while preserving checksum integrity.
5. Update Celery progress reporting to include evidence hydration milestones without bloating telemetry.
6. Enhance tests covering mixed evidence bundles, corruption detection, and idempotent rehydration.
7. Refresh worker and export route READMEs to document ingestion contracts and failure handling.

### 2. Orchestrate Role-Sequenced Approval Workflows With Delegation and SLA Awareness
Replace single-stage approvals with configurable ladders that respect role requirements, due dates, delegation, and rejection loops to ensure governance rigor.

**Key Actions**
1. Design SQLAlchemy models for stage definitions, including ordering, role requirements, SLAs, delegation, and audit metadata, plus Alembic migration.
2. Update schemas and console routes to initiate workflows, advance stages, reassign approvers, and record rejection/remediation cycles.
3. Integrate worker or scheduler hooks to detect overdue stages and trigger notifications or remediation callbacks.
4. Emit granular timeline events for stage transitions to guarantee traceability.
5. Redesign frontend approval panels into ladder visualizations with delegation controls and status cues.
6. Build backend and frontend tests simulating straight-through, delegated, and rejection workflows.
7. Update backend and frontend documentation with lifecycle, API, and operational guidance.

### 3. Introduce Scientist-Facing Narrative Sandbox and Diffable Previews
Empower scientists to preview dossier compositions before packaging, compare revisions, and annotate context to reduce downstream rework.

**Key Actions**
1. Map markdown rendering utilities and extend them for preview rendering with attachment placeholders.
2. Implement preview endpoints that render current narratives with inline evidence previews and optional diffing against prior exports.
3. Build a frontend previewer module with diff toggles, annotation entry, and readiness indicators.
4. Persist preview annotations in backend models and propagate them as timeline events.
5. Allow the packaging worker to ingest preview-approved annotations for manifest embedding.
6. Add integration tests ensuring preview parity and diff regression coverage.
7. Document preview workflows and best practices for scientists.

### 4. Provide Automation & CLI Tooling for Bulk Narrative Operations
Offer programmatic interfaces for bulk generation, regeneration, and compliance submissions, aligning with automation-first lab operations.

**Key Actions**
1. Catalog existing APIs to define CLI coverage targets.
2. Develop CLI utilities under `tools/` for authentication, batch exports, progress monitoring, retries, and artifact downloads with checksum validation.
3. Support template-driven regeneration workflows for post-protocol updates.
4. Implement machine-readable metadata outputs for integration with automation pipelines.
5. Add contract tests for CLI flows, including failure retries and artifact validation.
6. Document CLI usage in `tools/README.md` and cross-link from backend/front-end guides.

### 5. Codify Compliance Intelligence Without Telemetry Bloat
Aggregate lifecycle data into focused compliance insights and remediation triggers while maintaining lean data capture.

**Key Actions**
1. Define minimal event projections leveraging manifest digests and lifecycle timestamps.
2. Materialize aggregate views summarizing backlog, retry hotspots, approval latency, and retention expiries.
3. Expose compliance summary endpoints for dashboards and governance consumers.
4. Create frontend dashboard modules with SLA indicators and drill-down filters sourced from curated aggregates.
5. Wire automated remediation hooks for threshold breaches without expanding telemetry scope.
6. Validate integrity via tests covering aggregation correctness, SLA triggers, and dashboard rendering.
7. Update compliance documentation with insights, remediation flows, and data provenance guarantees.

### 6. Institutionalize Living Documentation & Operational Runbooks
Ensure rapidly evolving narrative systems remain understandable and operable by future contributors.

**Key Actions**
1. Audit current READMEs for accuracy relative to new worker, evidence, and approval flows.
2. Draft end-to-end runbooks covering packaging, evidence hydration, approvals, previews, and automation touchpoints.
3. Embed structured metadata comments in extended modules for machine readability.
4. Produce SOP-style guides in `/docs/` aligning scientist actions with system capabilities and remediation protocols.
5. Introduce reflection templates capturing learnings after major narrative releases.

## Next Steps
- Socialize this overview with engineering, scientific operations, and compliance stakeholders to prioritize execution order.
- Establish milestones and success metrics for each evolution track.
- Integrate the selected track workstreams into the existing progress and refinement plans.
