# Governance Timeline Lineage Widgets

- **File**: `ScenarioContextWidget.tsx`
- **Purpose**: renders structured scenario/notebook provenance metadata for override actions so console operators can trace governance decisions back to their originating artefacts.
- **Key behaviours**:
  - Accepts a `GovernanceOverrideLineageContext` payload and presents scenario and notebook details with timestamp and actor attribution.
  - Emits a dedicated container with `data-biolab-widget="governance-override-lineage"` for machine parsing by analytics agents.
  - Collapses when no lineage data is supplied, keeping the decision timeline compact for legacy entries.
- **Status**: pilot

Update this document if additional lineage widgets (e.g., reversal summaries, knowledge graph drill-ins) are introduced so renderers remain discoverable.
