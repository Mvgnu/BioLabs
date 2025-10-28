# Experiment Console Page

- **File**: `[executionId]/page.tsx`
- **Purpose**: renders live protocol execution data including step gating signals, telemetry, anomalies, and remediation CTAs.
- **Key behaviours**:
  - Consumes `blocked_reason`, `required_actions`, and `auto_triggers` from the backend to show orchestration banners per step.
  - Routes all remediation CTAs through the orchestrator endpoint `/api/experiment-console/sessions/{execution_id}/steps/{step_index}/remediate`, displaying per-action outcomes inline.
  - Provides an "Attempt Orchestrated Advance" button that calls `/api/experiment-console/sessions/{execution_id}/steps/{step_index}/advance` and reports blockers to the user when transitions fail.
  - The governance preview modal now hydrates a persistent scenario workspace by calling `/api/experiments/{execution_id}/scenarios`, rendering saved scenarios via `ScenarioSummary`, and supporting create/update/clone/delete flows (plus folder creation) in-line with the backend RBAC rules.
  - Scientists can organise scenarios into execution-scoped folders, toggle shared team visibility, bind previews to timeline events, and schedule expirations directly from the modal UI.
- The governance analytics panel (`components/Analytics/AnalyticsPanel`) queries `/api/governance/analytics` to surface SLA accuracy, blocker heatmaps, and ladder load metrics derived from preview telemetry and execution outcomes. Responses are now served from an in-process cache that invalidates whenever override actions or governance coaching notes change so the panel stays responsive without stale insights.
- `useGovernanceStream` hydrates `/api/experiment-console/governance/timeline/stream` over SSE, merging live reversal locks and cooldown ticks directly into the governance timeline caches so `DecisionTimeline` can render collaborative state in real time.
- **Action handling**:
  - Guided wizard collects context for booking creation/adjustments and equipment maintenance requests before invoking remediation.
  - Automatic remediation results (executed, scheduled, skipped, failed) are surfaced beneath the step banner with semantic colour coding.
  - Manual redirects now occur only when the backend reports an unsupported action.
- **Timeline intelligence**:
  - The `Timeline` component under `components/Timeline` virtualises event rows, fetches paginated history via `useExecutionTimeline`, and supports type filtering plus inline annotations stored client-side for coaching notes.
  - When the dedicated timeline endpoint is still loading the initial page, the UI hydrates using `timeline_preview` from the session payload to keep the narrative responsive.
  - The `ExportsPanel` component surfaces persisted narrative exports, allows scientists to bundle recent events as evidence, and captures approval signatures that post back to the backend export endpoints.
  - `PreviewModal` provides a governance preview workflow that drives the `/api/experiments/{execution_id}/preview` endpoint, storing scenario history in `localStorage` and coordinating persisted scenarios through the new folder and sharing-aware workspace APIs. It also consumes `useGovernanceRecommendations` to fetch `/api/governance/recommendations/override`, rendering priority-labelled banners with cadence metrics and inline acknowledgement toggles for operators.

Update this README whenever step gating semantics or CTA routing logic changes.
