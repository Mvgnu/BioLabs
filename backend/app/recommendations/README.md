# Governance Recommendations Module

- purpose: generate deterministic governance override recommendations from cadence analytics
- scope: FastAPI-facing helpers that translate analytics payloads into staffing advisories and persist audit events
- status: pilot

`governance.py` wraps the reviewer cadence aggregation helpers to construct `GovernanceOverrideRecommendationReport` payloads. Rules inspect reviewer load bands, latency percentiles, blocker ratios, churn signals, and publish streak alerts to emit actionable overrides (`reassign`, `cooldown`, `escalate`). Each recommendation captures metrics, RBAC-scoped reviewer context, and related execution identifiers. The module also logs recommendation provenance via `record_governance_recommendation_event` so governance operators retain a full audit trail of generated advice.

`actions.py` centralizes override workflow execution, persisting `GovernanceOverrideAction` rows when operators accept, decline, execute, or reverse staffing overrides. Helpers enforce idempotent mutations via execution hashes, update affected baselines (including reversal rollbacks), guard reversals with short-lived row-level lock tokens enriched with escalation tier metadata to prevent concurrent operators from double-submitting, and emit enriched event payloads (including `cooldown_window_minutes`) plus lock lifecycle notifications for downstream subscribers.

`timeline.py` composes the governance decision timeline feed by blending override recommendation events, override outcomes, baseline lifecycle events, and cadence analytics snapshots. It enforces RBAC-aware joins, emits structured `GovernanceDecisionTimelineEntry` payloads, and supplies cursor-based pagination helpers for the experiment console.

