# Backend Application Layer

This directory contains the FastAPI application modules that power BioLabs server capabilities. Key areas include:

- `routes/`: HTTP handlers grouped by functional surface areas.
- `models.py`: SQLAlchemy ORM definitions for persistent entities.
- `schemas.py`: Pydantic schemas for request validation and response shaping.
- `narratives.py`: Markdown narrative serialization for experiment execution exports.
- Supporting helpers for authentication, notifications, orchestration, and integrations.

## Narrative Exports

The `narratives.py` module transforms ordered `ExecutionEvent` streams into compliance-ready Markdown dossiers. Exports are triggered through the experiment console API (`POST /api/experiment-console/sessions/{execution_id}/exports/narrative`) and logged as timeline events for traceability. Each export now persists to `execution_narrative_exports` with bundled evidence attachments (timeline events, files, notebook entries, analytics snapshots, QC metrics, remediation reports), staged approval metadata, version history, and packaged artifact lifecycle metadata accessible via `GET /api/experiment-console/sessions/{execution_id}/exports/narrative`. Packaging jobs are dispatched to the Celery worker in `workers/packaging.py`, which retries failures, increments attempt counters, hydrates notebook markdown and event payload archives, records digest metadata, and enforces retention windows. Scientists can download generated packages via `GET /api/experiment-console/sessions/{execution_id}/exports/narrative/{export_id}/artifact`, which verifies stored checksums before streaming data and raises lifecycle events for expirations or integrity failures. Durable storage helpers (`storage.py`) now generate namespaced paths, optional signed URLs, and checksum validation to guard against drift.

Multi-stage approvals are orchestrated by the experiment console routes: `POST /api/experiment-console/sessions/{execution_id}/exports/narrative/{export_id}/approve` advances the active stage with signature capture and emits timeline events (`narrative_export.approval.stage_started`, `.stage_completed`, `.finalized`, `.rejected`). Delegations (`POST .../stages/{stage_id}/delegate`) and remediation resets (`POST .../stages/{stage_id}/reset`) update assignees, SLA due dates, and action history while keeping React Query caches synchronized. Celery monitors for SLA breaches via `monitor_narrative_approval_slas`, raising `narrative_export.approval.stage_overdue` when deadlines lapse. Evidence discovery routes (`GET /api/notebook/entries/evidence` and `GET /api/data/evidence`) provide paginated descriptors for console attachment pickers, while `/api/experiment-console/exports/narrative/jobs` continues to surface queue telemetry for operations teams.

## Testing

Use `pytest` to execute backend unit tests:

```bash
pytest backend/app/tests
```

The new narrative export flow is covered by `test_generate_execution_narrative_export` inside `tests/test_experiment_console.py`.
