# Governance Timeline Lineage Widgets

- **File**: `ScenarioContextWidget.tsx`
- **Purpose**: renders structured scenario/notebook provenance metadata for override actions so console operators can trace governance decisions back to their originating artefacts.
- **Key behaviours**:
  - Accepts a `GovernanceOverrideLineageContext` payload and presents scenario and notebook details with timestamp and actor attribution.
  - Emits a dedicated container with `data-biolab-widget="governance-override-lineage"` for machine parsing by analytics agents.
  - Collapses when no lineage data is supplied, keeping the decision timeline compact for legacy entries.
- **Status**: pilot

- **File**: `AnalyticsLineageWidget.tsx`
- **Purpose**: visualises aggregated override lineage analytics (scenario and notebook buckets) inside the governance timeline so operators can quickly gauge lineage impact.
- **Key behaviours**:
  - Normalises analytics payload counts before rendering dual-column bucket lists with execution/reversal totals.
  - Emits a container tagged `data-biolab-widget="governance-lineage-analytics"` for downstream telemetry capture.
  - Hides itself automatically when no lineage aggregates are present to avoid empty chrome.
- **Status**: pilot

Update this document if additional lineage widgets (e.g., reversal summaries, knowledge graph drill-ins) are introduced so renderers remain discoverable.
