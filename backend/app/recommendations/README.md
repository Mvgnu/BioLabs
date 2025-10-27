# Governance Recommendations Module

- purpose: generate deterministic governance override recommendations from cadence analytics
- scope: FastAPI-facing helpers that translate analytics payloads into staffing advisories and persist audit events
- status: pilot

`governance.py` wraps the reviewer cadence aggregation helpers to construct `GovernanceOverrideRecommendationReport` payloads. Rules inspect reviewer load bands, latency percentiles, blocker ratios, churn signals, and publish streak alerts to emit actionable overrides (`reassign`, `cooldown`, `escalate`). Each recommendation captures metrics, RBAC-scoped reviewer context, and related execution identifiers. The module also logs recommendation provenance via `record_governance_recommendation_event` so governance operators retain a full audit trail of generated advice.
