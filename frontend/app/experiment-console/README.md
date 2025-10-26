# Experiment Console Page

- **File**: `[executionId]/page.tsx`
- **Purpose**: renders live protocol execution data including step gating signals, telemetry, anomalies, and remediation CTAs.
- **Key behaviours**:
  - Consumes `blocked_reason`, `required_actions`, and `auto_triggers` from the backend to show orchestration banners per step.
  - Routes all remediation CTAs through the orchestrator endpoint `/api/experiment-console/sessions/{execution_id}/steps/{step_index}/remediate`, displaying per-action outcomes inline.
  - Provides an "Attempt Orchestrated Advance" button that calls `/api/experiment-console/sessions/{execution_id}/steps/{step_index}/advance` and reports blockers to the user when transitions fail.
- **Action handling**:
  - Guided wizard collects context for booking creation/adjustments and equipment maintenance requests before invoking remediation.
  - Automatic remediation results (executed, scheduled, skipped, failed) are surfaced beneath the step banner with semantic colour coding.
  - Manual redirects now occur only when the backend reports an unsupported action.
- **Timeline intelligence**:
  - The `Timeline` component under `components/Timeline` virtualises event rows, fetches paginated history via `useExecutionTimeline`, and supports type filtering plus inline annotations stored client-side for coaching notes.
  - When the dedicated timeline endpoint is still loading the initial page, the UI hydrates using `timeline_preview` from the session payload to keep the narrative responsive.

Update this README whenever step gating semantics or CTA routing logic changes.
