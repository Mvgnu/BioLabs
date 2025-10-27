# Experiment Console Governance Analytics

- purpose: document analytics visualisations rendered inside the experiment console
- scope: React components that consume `/api/governance/analytics` responses
- status: pilot

## Components

- `AnalyticsPanel.tsx` – orchestrates SLA, blocker, ladder load, and baseline lifecycle widgets using the governance analytics hook.
- `BaselineLifecycleStats.tsx` – renders the "Baseline Lifecycle Pulse" card, highlighting approval latency, publication cadence, and rollback counts derived from analytics payloads.
- `SlaAccuracyChart.tsx`, `BlockerHeatmap.tsx`, `LadderLoadChart.tsx` – existing visualisations for preview health signals.

All components expect data normalised via `governanceApi.getAnalytics`, which now maps baseline lifecycle metrics into numeric form. When adding new widgets, extend this README with purpose/inputs/outputs metadata.
