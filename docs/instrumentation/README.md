# Instrumentation Orchestration

The instrumentation service coordinates robotic device reservations, execution telemetry, and SOP governance.

## Service Overview

- **Service module**: `backend/app/services/instrumentation.py`
- **API module**: `backend/app/routes/instrumentation.py`
- **Schemas**: `backend/app/schemas/instrumentation.py`

### Capabilities

`POST /api/instrumentation/instruments/{equipment_id}/capabilities`
: Register structured capability descriptors with guardrail requirements so UI planners understand supported run envelopes and governance prerequisites.

`POST /api/instrumentation/instruments/{equipment_id}/sops`
: Attach SOP revisions to an instrument, reflecting their lifecycle state. Responses include effective and retired timestamps for audit surfaces.

### Scheduling & Execution

`POST /api/instrumentation/instruments/{equipment_id}/reservations`
: Books execution windows, captures requested run parameters, and records custody guardrail snapshots. Critical escalations convert the reservation to `guardrail_blocked` so teams clear policies before dispatch.

`POST /api/instrumentation/reservations/{reservation_id}/dispatch`
: Transitions a reservation into an active run while merging runtime overrides and inheriting guardrail flags.

`POST /api/instrumentation/runs/{run_id}/status`
: Updates run lifecycle and synchronizes the linked reservation state. Completed or failed runs stamp timestamps for digital twins.

`POST /api/instrumentation/runs/{run_id}/telemetry`
: Streams deterministic telemetry envelopes for SSE layers and analytics.

`GET /api/instrumentation/runs/{run_id}/telemetry`
: Returns run metadata plus ordered telemetry samples for replay dashboards.

`POST /api/instrumentation/instruments/{equipment_id}/simulate`
: Produces a deterministic reservation/run pair and emits a sequence of simulation events (telemetry and status checkpoints)
  for digital twin dashboards, Celery workers, and SSE relays. The simulation harness reuses the guardrail gating logic to
  mirror real dispatch behavior.

### Digital Twin UI

The Next.js dashboard under `frontend/app/instrumentation/` visualizes instrument status, guardrail context, simulation
controls, and telemetry timelines. React Query hooks in `frontend/app/hooks/useInstrumentation.ts` coordinate data fetching
and simulation triggering while maintaining machine-readable metadata comments for downstream automation.

### Guardrail Integration

Guardrail snapshots source active custody escalations for the associated team. Reservations with open critical escalations are blocked, while lower severities switch to `pending_clearance` so operations teams can proceed once mitigations close.

### Testing

Unit coverage resides in `backend/app/tests/test_instrumentation.py`, exercising capability registration, SOP linkage, reservation conflicts, guardrail blocking, telemetry streaming, and lifecycle updates.
