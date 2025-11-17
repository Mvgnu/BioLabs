## Problem Statement
Experiment console narrative export approvals were failing under the sqlite test harness due to `OperationalError: database is locked` when the Celery packaging task attempted to insert execution events while the API request session still held an open transaction.

## Metadata
Status: Resolved
Priority: High
Type: Test
Next_Target: backend/app/routes/experiment_console.py
Last_Tool: pytest backend/app/tests/test_experiment_console.py -q

## Current Hypothesis
The synchronous Celery packaging call reused the global sqlite database file while the FastAPI request session maintained an open transaction, causing insert attempts from the worker session to block. Releasing the request session before running the packaging routine and reloading the export from a fresh session should eliminate the lock while preserving deterministic artifact availability for the response payload.

## Log of Attempts (Chronological)
- 2025-01-15 18:02 UTC: Reproduced failures in `test_generate_execution_narrative_export` showing sqlite lock errors triggered by `package_execution_narrative_export` commits.
- 2025-01-15 18:20 UTC: Added sqlite connection timeouts and refactored the approval route to queue packaging after closing the original session, reloading the export with a fresh session to build the response payload without background task delays.
- 2025-01-15 18:32 UTC: Confirmed `pytest backend/app/tests/test_experiment_console.py -q` passes with packaging completing synchronously and no lock errors.

## Resolution Summary
The approval endpoint now captures queued export identifiers, commits guardrail state, closes the request session before invoking `enqueue_narrative_export_packaging`, and reloads the export using a new `SessionLocal` context to build the response. Combined with sqlite connection timeouts, this releases locks prior to worker inserts while keeping artifacts immediately available for callers.
