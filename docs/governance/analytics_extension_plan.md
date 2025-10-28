# Governance Analytics Serializer Extension

- purpose: capture the serializer and reporting changes required to surface overdue-stage analytics, breach trends, and actionable guardrail insights
- status: draft
- updated: 2025-07-05
- related_docs: docs/governance/export_enforcement_audit.md, docs/approval_workflow_design.md

## Current State Summary
- `backend/app/analytics/governance.py` materializes cached `GovernanceAnalyticsReport` payloads with stage metrics stored under `report.meta["approval_stage_metrics"]` via `_collect_stage_metrics` and `_include_stage_metrics`. These metrics already track counts, overdue flags, and resolution timing, but nothing aggregates across executions.【F:backend/app/analytics/governance.py†L128-L205】
- Reviewer cadence data is accumulated via `_summarize_override_events` and friends, yet breach trends (frequency over time, SLA deltas) are absent and overdue counts stay per-export.【F:backend/app/analytics/governance.py†L300-L456】

## Required Schema Additions
1. **Meta Overdue Summary**: Extend `schemas.GovernanceAnalyticsReport` (and corresponding frontend types) with a new `overdue_summary` object capturing:
   - `total_overdue_exports`
   - `total_overdue_stages`
   - `mean_overdue_minutes`
   - `stage_status_breakdown` keyed by status + breach state
2. **Breach Trend Buckets**: Add `breach_trends` arrays summarizing counts grouped by `day` or `week` plus `stage_index`. Calculated server-side to avoid frontend aggregation drift.
3. **Actionable Tooltips**: Serialize `stage_details` with `breach_reason_codes` once guardrail simulations record structured reasons, enabling UI hover tooltips.

## Backend Implementation Notes
- Introduce helper `_aggregate_overdue_metrics(exports: Iterable[ExecutionNarrativeExport]) -> dict[str, Any]` that iterates over `_collect_stage_metrics` outputs and populates the new meta fields.
- Modify `_include_stage_metrics` to call the aggregator and attach `report.meta["overdue_summary"]` & `report.meta["breach_trends"]` alongside existing per-export metrics.【F:backend/app/analytics/governance.py†L188-L205】
- Update `schemas.GovernanceAnalyticsReport` plus Pydantic validators to accept the new structures.
- Ensure cache invalidation continues to trigger via `invalidate_governance_analytics_cache` with the same execution IDs; no key changes required.【F:backend/app/analytics/governance.py†L206-L267】

## Testing Strategy
- Extend `backend/app/tests/test_governance.py` (or create dedicated analytics tests) to seed exports with staged overdue flags and verify aggregated totals.
- Add regression coverage for cache hits vs. misses to guarantee new fields persist between calls.
- Provide JSON schema snapshots for frontend contract tests once TypeScript types update.

## Frontend/UX Hooks
- Frontend governance dashboards should read `meta.overdue_summary` for overdue tiles and trending charts.
- Experiment console tooltip components need new copy referencing `breach_reason_codes` and SLA minutes.

## Follow-Up Documentation
- Update operator SOPs once dashboards surface the new analytics.
- Cross-link this document from future reflections after the analytics iteration ships.
