# Backend Application Layer

This directory contains the FastAPI application modules that power BioLabs server capabilities. Key areas include:

- `routes/`: HTTP handlers grouped by functional surface areas.
- `models.py`: SQLAlchemy ORM definitions for persistent entities.
- `schemas.py`: Pydantic schemas for request validation and response shaping.
- `narratives.py`: Markdown narrative serialization for experiment execution exports.
- Supporting helpers for authentication, notifications, orchestration, and integrations.

## Narrative Exports

The `narratives.py` module transforms ordered `ExecutionEvent` streams into compliance-ready Markdown dossiers. Exports are triggered through the experiment console API (`POST /api/experiment-console/sessions/{execution_id}/exports/narrative`) and logged as timeline events for traceability. Each export now persists to `execution_narrative_exports` with bundled evidence attachments, approval metadata, version history, and packaged artifact lifecycle metadata accessible via `GET /api/experiment-console/sessions/{execution_id}/exports/narrative`. Packaging jobs are dispatched to the Celery worker in `workers/packaging.py`, which retries failures, increments attempt counters, records digest metadata, and enforces retention windows. Scientists can download generated packages via `GET /api/experiment-console/sessions/{execution_id}/exports/narrative/{export_id}/artifact`, which verifies stored checksums before streaming data and raises lifecycle events for expirations or integrity failures. Durable storage helpers (`storage.py`) now generate namespaced paths, optional signed URLs, and checksum validation to guard against drift. Compliance signatures remain available through `POST /api/experiment-console/sessions/{execution_id}/exports/narrative/{export_id}/approve`, which records approval or rejection events on the execution timeline, and `/api/experiment-console/exports/narrative/jobs` surfaces queue telemetry for operations teams.

## Testing

Use `pytest` to execute backend unit tests:

```bash
pytest backend/app/tests
```

The new narrative export flow is covered by `test_generate_execution_narrative_export` inside `tests/test_experiment_console.py`.
