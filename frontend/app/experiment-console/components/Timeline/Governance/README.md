# Governance Decision Timeline

- **File**: `DecisionTimeline.tsx`
- **Purpose**: renders the composite governance decision feed blending override recommendations, override outcomes, baseline lifecycle events, and cadence analytics snapshots for the experiment console sidebar.
- **Key behaviours**:
  - Displays entry badges with contextual colours per entry type (`override_recommendation`, `override_action`, `baseline_event`, `analytics_snapshot`, and `coaching_note`).
  - Presents actor/timestamp metadata and renders up to six detail fields using a compact definition list to highlight critical payload attributes without overwhelming the UI.
  - Supports incremental pagination by exposing a "Load more" control wired to the feed hook so future realtime invalidation can reuse the same component contract.
  - Surfaces override lineage context via `Lineage/ScenarioContextWidget` to expose scenario/notebook provenance alongside raw detail payloads.
- Renders aggregated lineage analytics via `Lineage/AnalyticsLineageWidget` when timeline entries include a `lineage_summary` payload.
- Provides inline override reversal controls that open a confirmation form, post to the governance reversal API via `useReverseGovernanceOverride`, and surface cooldown messaging with structured diffs rendered by `ReversalDiffViewer.tsx`.
 - Provides inline override reversal controls that open a confirmation form, post to the governance reversal API via `useReverseGovernanceOverride`, and surface cooldown messaging with structured diffs rendered by `ReversalDiffViewer.tsx`, including the configured cooldown window minutes when present. Concurrency lock errors returned by the API are surfaced inline via the reversal form error state so operators know another reversal is already in progress.
- **Status**: pilot

Update this document if you introduce new entry types, alter badge styling, or add interactive affordances (e.g., inline reversals or notebook linking) so downstream agents understand the rendering contract.
