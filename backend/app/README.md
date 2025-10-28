# Backend Application Layer

This directory contains the FastAPI application modules that power BioLabs server capabilities. Key areas include:

- `routes/`: HTTP handlers grouped by functional surface areas.
- `models.py`: SQLAlchemy ORM definitions for persistent entities.
- `schemas.py`: Pydantic schemas for request validation and response shaping.
- `analytics/`: Aggregation utilities turning execution telemetry into governance dashboards.
- `narratives.py`: Markdown narrative serialization for experiment execution exports.
- `routes/governance.py`: Administrative APIs for workflow template management and assignments.
- Supporting helpers for authentication, notifications, orchestration, and integrations.

## Narrative Exports

The `narratives.py` module transforms ordered `ExecutionEvent` streams into compliance-ready Markdown dossiers. Exports are triggered through the experiment console API (`POST /api/experiment-console/sessions/{execution_id}/exports/narrative`) and logged as timeline events for traceability. Each export now persists to `execution_narrative_exports` with bundled evidence attachments (timeline events, files, notebook entries, analytics snapshots, QC metrics, remediation reports), staged approval metadata, version history, and packaged artifact lifecycle metadata accessible via `GET /api/experiment-console/sessions/{execution_id}/exports/narrative`. Packaging jobs are dispatched to the Celery worker in `workers/packaging.py`, which retries failures, increments attempt counters, hydrates notebook markdown and event payload archives, records digest metadata, and enforces retention windows. Scientists can download generated packages via `GET /api/experiment-console/sessions/{execution_id}/exports/narrative/{export_id}/artifact`, which verifies stored checksums before streaming data and raises lifecycle events for expirations or integrity failures. Durable storage helpers (`storage.py`) now generate namespaced paths, optional signed URLs, and checksum validation to guard against drift.

Governance preview runs now emit `governance.preview.summary` analytics events via the experiment console routes. The `analytics/governance.py` module fuses these summaries with execution step completions to compute SLA accuracy, blocker trends, and ladder load metrics returned by `/api/governance/analytics`. These responses are cached for 30 seconds per user/team scope and invalidated when override actions or coaching notes mutate execution state, keeping the endpoint fast while preserving freshness.

Multi-stage approvals are orchestrated by the experiment console routes: `POST /api/experiment-console/sessions/{execution_id}/exports/narrative/{export_id}/approve` advances the active stage with signature capture and emits timeline events (`narrative_export.approval.stage_started`, `.stage_completed`, `.finalized`, `.rejected`). Delegations (`POST .../stages/{stage_id}/delegate`) and remediation resets (`POST .../stages/{stage_id}/reset`) update assignees, SLA due dates, and action history while keeping React Query caches synchronized. Celery monitors for SLA breaches via `monitor_narrative_approval_slas`, raising `narrative_export.approval.stage_overdue` when deadlines lapse. Evidence discovery routes (`GET /api/notebook/entries/evidence` and `GET /api/data/evidence`) provide paginated descriptors for console attachment pickers, while `/api/experiment-console/exports/narrative/jobs` continues to surface queue telemetry for operations teams.

Scientist-facing previews are handled by the new `/api/experiments/{execution_id}/preview` endpoint located in `routes/experiment_console.py`. The route composes immutable governance snapshots with ladder simulations from `simulation.py`, renders Markdown via `render_preview_narrative`, records telemetry in `GovernanceTemplateAuditLog`, and returns `ExperimentPreviewResponse` payloads for UI diffing.

## Governance Workflow Templates

Compliance administrators can now curate reusable approval ladders through the governance API surface:

- `POST /api/governance/templates` creates published or draft templates, automatically versioning when reusing an existing `template_key` or specifying `forked_from_id`. Each new version retires the previous latest while preserving lineage metadata.
- `GET /api/governance/templates` (and `/api/governance/templates/{id}`) surfaces template details, including stage blueprints, permitted roles, SLA defaults, and publication status. The optional `include_all` query flag returns historical versions for auditing.
- `POST /api/governance/templates/{id}/assignments` links templates to teams or protocol templates, allowing contextual rollout of governance policies. Assignments can be enumerated via `GET /api/governance/templates/{id}/assignments` and revoked through `DELETE /api/governance/assignments/{assignment_id}`.

Templates persist to `execution_narrative_workflow_templates` with JSON-encoded stage blueprints and SLA metadata, while assignments live in `execution_narrative_workflow_template_assignments`. Narrative exports referencing a template now require immutable published snapshots sourced from `execution_narrative_workflow_template_snapshots`, ensuring lifecycle enforcement and drift detection. Published/archived transitions emit structured audit entries inside `governance_template_audit_logs` for review.

## Baseline Governance Lifecycle

Baseline submissions are now catalogued via `/api/governance/baselines`. Scientists can submit execution-tied proposals with reviewer assignments, reviewers can approve or reject, and authorized actors can publish approved baselines, promoting them to the active standard (`is_current=True`) while versioning per protocol template. Admins retain the ability to roll back published baselines and optionally reinstate a prior version. All transitions generate `GovernanceBaselineEvent` rows through `record_baseline_event` for auditability. See `docs/governance/baselines.md` for workflow details and RBAC expectations.

### Governance CLI

- Run `python -m backend.app.cli migrate-exports` to backfill historical narrative exports with published snapshot identifiers. Use `--dry-run` to preview impact without applying updates.
- Migration anomalies are appended to `problems/governance_migration.log` for triage alongside broader Problem Tracker workflows.

## Testing

Use `pytest` to execute backend unit tests:

```bash
pytest backend/app/tests
```

The new narrative export flow is covered by `test_generate_execution_narrative_export` inside `tests/test_experiment_console.py`.
