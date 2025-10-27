# Governance Analytics Module

- purpose: aggregate governance preview telemetry with execution outcomes for dashboards and policy decisions
- scope: reusable analytics utilities for experiment console governance features
- status: pilot

This package currently exposes `governance.py`, which condenses preview ladder insights, execution step completions, and baseline lifecycle cadence into `GovernanceAnalyticsReport` payloads. These payloads power the `/api/governance/analytics` endpoint and drive SLA accuracy, blocker heatmaps, ladder load visualisations, and baseline approval/publishing intelligence on the experiment console. Reviewer cadence totals now include percentile latency guardrails and load band histograms so downstream clients can surface staffing KPIs without reprocessing raw samples.

## Reviewer Cadence Summary

- purpose: deliver RBAC-safe reviewer throughput analytics suitable for staffing dashboards
- payloads: `GovernanceAnalyticsReport` (full view) and `GovernanceReviewerCadenceReport` (lean reviewer view)
- instrumentation: latency samples reuse baseline `submitted_at`, `reviewed_at`, and publish timestamps; no additional tracking tables introduced
- RBAC: all events are filtered against `_get_user_team_ids`, and reviewer identities are revalidated against team membership unless the requester is an administrator.

Each reviewer record includes:

- `load_band` derived from assignment + pending volume (`light`, `steady`, `saturated`).
- `latency_p50_minutes` and `latency_p90_minutes` computed via linear interpolation.
- `blocked_ratio_trailing` and `churn_signal` summarising blocker intensity and baseline churn without exposing cross-team identifiers.
- `publish_streak` plus `streak_alert` (>=3 publishes within 72 hours).

Aggregate guardrails accompany the reviewer list:

- `GovernanceReviewerLoadBandCounts` summarises load distribution for heatmap primitives.
- `reviewer_latency_p50_minutes`/`p90` expose staffing guardrails derived from pooled reviewer latency samples.
- `streak_alert_count` surfaces operators requiring attention while maintaining minimal payload size.

The `/api/governance/analytics` route accepts `view=reviewer` to omit preview summaries when only cadence data is required. The lean response reuses the same RBAC filters and returns `GovernanceReviewerCadenceReport` (reviewers + totals) for hooks such as `useReviewerCadence`. Document KPI additions and RBAC adjustments here with instrumentation intent and metadata tags whenever new governance metrics ship.
