# Worker Modules

The `backend/app/workers` package houses Celery tasks that execute BioLabs
workloads outside of the FastAPI request lifecycle. Workers are responsible for
durable job orchestration, retries, and lifecycle telemetry. Current modules:

- `packaging.py` – processes execution narrative export packaging, emitting
  progress events, persisting lifecycle metadata, validating artifact
  integrity, and hydrating multi-domain evidence (files, notebook entries,
  analytics snapshots, QC metrics, remediation reports) into the manifest.

Workers share the global Celery application configured in `tasks.py`. They
should remain idempotent, tolerate retries, and emit machine-readable
annotations for downstream compliance systems.
