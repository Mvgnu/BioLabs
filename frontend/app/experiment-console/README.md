# Experiment Console Page

- **File**: `[executionId]/page.tsx`
- **Purpose**: renders live protocol execution data including step gating signals, telemetry, anomalies, and remediation CTAs.
- **Key behaviours**:
  - Consumes `blocked_reason`, `required_actions`, and `auto_triggers` from the backend to show orchestration banners per step.
  - Dispatches remediation actions based on the `domain:verb:identifier` pattern (inventory recovery, equipment maintenance, booking/compliance follow-ups).
  - Provides an "Attempt Orchestrated Advance" button that calls `/api/experiment-console/sessions/{execution_id}/steps/{step_index}/advance` and reports blockers to the user when transitions fail.
- **Action handling**:
  - Inventory restoration triggers `PUT /api/inventory/items/{id}` with `status: available`.
  - Equipment maintenance CTAs schedule calibration/maintenance tasks through `/api/equipment/maintenance`.
  - Booking/compliance actions currently redirect to their respective consoles for manual follow-up.

Update this README whenever step gating semantics or CTA routing logic changes.
