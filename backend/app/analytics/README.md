# Governance Analytics Module

- purpose: aggregate governance preview telemetry with execution outcomes for dashboards and policy decisions
- scope: reusable analytics utilities for experiment console governance features
- status: pilot

This package currently exposes `governance.py`, which condenses preview ladder insights, execution step completions, and baseline lifecycle cadence into `GovernanceAnalyticsReport` payloads. These payloads power the `/api/governance/analytics` endpoint and drive SLA accuracy, blocker heatmaps, ladder load visualisations, and baseline approval/publishing intelligence on the experiment console. Future analytics surfaces should live in this directory alongside structured metadata comments to remain machine-parseable.
