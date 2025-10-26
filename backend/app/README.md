# Backend Application Layer

This directory contains the FastAPI application modules that power BioLabs server capabilities. Key areas include:

- `routes/`: HTTP handlers grouped by functional surface areas.
- `models.py`: SQLAlchemy ORM definitions for persistent entities.
- `schemas.py`: Pydantic schemas for request validation and response shaping.
- `narratives.py`: Markdown narrative serialization for experiment execution exports.
- Supporting helpers for authentication, notifications, orchestration, and integrations.

## Narrative Exports

The `narratives.py` module transforms ordered `ExecutionEvent` streams into compliance-ready Markdown dossiers. Exports are triggered through the experiment console API (`POST /api/experiment-console/sessions/{execution_id}/exports/narrative`) and logged as timeline events for traceability. Each export now persists to `execution_narrative_exports` with bundled evidence attachments, approval metadata, version history, and packaged artifact metadata accessible via `GET /api/experiment-console/sessions/{execution_id}/exports/narrative`. Background packaging writes zipped dossiers (Markdown narrative, attachments manifest, and referenced files) to the shared file store and exposes readiness through `artifact_status` and checksum fields. Scientists can download the generated packages via `GET /api/experiment-console/sessions/{execution_id}/exports/narrative/{export_id}/artifact`. Compliance signatures are captured through `POST /api/experiment-console/sessions/{execution_id}/exports/narrative/{export_id}/approve`, which records approval or rejection events on the execution timeline.

## Testing

Use `pytest` to execute backend unit tests:

```bash
pytest backend/app/tests
```

The new narrative export flow is covered by `test_generate_execution_narrative_export` inside `tests/test_experiment_console.py`.
