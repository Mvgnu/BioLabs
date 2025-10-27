# Governance Analytics Module

- purpose: aggregate governance preview telemetry with execution outcomes for dashboards and policy decisions
- scope: reusable analytics utilities for experiment console governance features
- status: pilot

This package currently exposes `governance.py`, which condenses preview ladder insights, execution step completions, and baseline lifecycle cadence into `GovernanceAnalyticsReport` payloads. These payloads power the `/api/governance/analytics` endpoint and drive SLA accuracy, blocker heatmaps, ladder load visualisations, and baseline approval/publishing intelligence on the experiment console.

## Reviewer Cadence Summary

- purpose: deliver RBAC-safe reviewer throughput analytics suitable for staffing dashboards
- payload: `reviewer_cadence` list of `GovernanceReviewerCadenceSummary`
- instrumentation: latency samples reuse baseline `submitted_at`, `reviewed_at`, and publish timestamps; no additional tracking tables introduced

Each reviewer record includes:

- `load_band` derived from assignment + pending volume (`light`, `steady`, `saturated`).
- `latency_p50_minutes` and `latency_p90_minutes` computed via linear interpolation.
- `blocked_ratio_trailing` and `churn_signal` summarising blocker intensity and baseline churn without exposing cross-team identifiers.
- `publish_streak` plus `streak_alert` (>=3 publishes within 72 hours).

The `/api/governance/analytics` route now accepts `view=reviewer` to omit preview summaries when only cadence data is required, shrinking payloads for RBAC dashboards. All reviewer identities are filtered via `_get_user_team_ids` membership checks unless the requesting user is an administrator.

Future analytics surfaces should live in this directory alongside structured metadata comments to remain machine-parseable. Extend this README with KPI guardrails and instrumentation rationale whenever new governance metrics are introduced.
