# Experiment Console Governance Analytics

- purpose: document analytics visualisations rendered inside the experiment console
- scope: React components that consume `/api/governance/analytics` responses
- status: pilot

## Components

- `AnalyticsPanel.tsx` – orchestrates SLA, blocker, ladder load, and baseline lifecycle widgets using the governance analytics hook.
- `BaselineLifecycleStats.tsx` – renders the "Baseline Lifecycle Pulse" card, highlighting approval latency, publication cadence, rollback counts, and the blocker churn index derived from analytics payloads.
- `SlaAccuracyChart.tsx`, `BlockerHeatmap.tsx`, `LadderLoadChart.tsx` – existing visualisations for preview health signals.
- `ReviewerLoadHeatmap.tsx` – tabulates reviewer assignments, completions, latency bands, and churn-weighted blocker signals to visualise throughput hotspots.
- `ReviewerStreakAlerts.tsx` – lists publish streak alerts generated when reviewers exceed three publishes inside a 72-hour window, enabling proactive staffing or overrides.

All components expect data normalised via `governanceApi.getAnalytics`, which now maps baseline lifecycle metrics into numeric form. When adding new widgets, extend this README with purpose/inputs/outputs metadata.
