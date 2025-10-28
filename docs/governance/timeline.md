# Governance Timeline Lineage Contracts

## Overview

The governance decision timeline now surfaces override lineage data alongside analytics snapshots and captures override reversal events with cooldown metadata. Override actions must include lineage payloads describing the originating scenario and/or notebook entries so that analytics can aggregate activity by provenance. A dedicated Alembic migration (`7c8d21f34abc_backfill_override_lineage.py`) backfills historical override records that were missing lineage rows by extracting any preserved detail snapshots, migration `8d4f6c7a9b01_override_reversal_events.py` introduces structured reversal event storage, and migration `20241005_01_reversal_cooldown_window_and_locks.py` adds explicit cooldown window tracking with reversal lock columns to prevent concurrent reversals.

## Data Contract

- **Requests**: Override write APIs (`accept`, `execute`, `decline`) require a `lineage` object with at least one of `scenario_id` or `notebook_entry_id`. Reversal APIs accept optional `metadata.cooldown_minutes` to enforce a post-reversal cooldown window.
- **Persistence**: `governance_override_lineages` stores scenario/notebook snapshots, capture metadata, and tags the `metadata` JSON with `"backfilled": true` for rows created by the migration.
- **Reversal Storage**: `governance_override_reversal_events` retains reversal actor attribution, baseline linkage, cooldown expiry, the configured cooldown window minutes, and a JSON diff between the original override detail snapshot and the reversal output. The ORM exposes this payload via `GovernanceOverrideAction.reversal_event_payload` for API serialization.
- **Response Fields**: Timeline API consumers receive `detail.cooldown_window_minutes` whenever a reversal sets a cooldown duration. This mirrors `reversal_event.cooldown_window_minutes` and should be surfaced in UI copy where operators expect to see the enforced window length.
- **Analytics**: `compute_governance_analytics` aggregates lineage activity into scenario and notebook buckets. These aggregates are embedded in timeline analytics entries under `detail.lineage_summary`.
- **Coaching Notes**: `governance_coaching_notes` persists threaded reviewer context with `thread_root_id`, `parent_id`, and `moderation_state` columns. API responses expose `metadata`, `reply_count`, and actor summaries to support optimistic UI updates and inline moderation cues.
- **Coaching Endpoints**: `/api/governance/overrides/{override_id}/coaching-notes` (GET/POST) and `/api/governance/coaching-notes/{note_id}` (PATCH) provide CRUD access with RBAC enforcement derived from override actors, execution owners, or baseline/template team membership.
- **Timeline Serialization**: Coaching notes appear in the decision timeline with `entry_type="coaching_note"`, carrying `detail` payloads that include the note body, moderation state, thread identifiers, and reply counts for progress indicators.

## Backfill Limitations

- Backfill only occurs when historical `detail_snapshot` payloads expose a `lineage`, `scenario`, or `notebook_entry` object. Overrides without any provenance in their stored detail remain without lineage.
- Snapshot metadata is reconstructed best-effort; missing `id` fields or stale titles are preserved as-is. Operators should audit critical overrides manually if downstream analytics look incomplete.

## Frontend Rendering

- `ScenarioContextWidget` continues to render per-entry lineage context.
- `AnalyticsLineageWidget` visualises aggregated scenario/notebook override counts using the `lineage_summary` payload.
- `ReversalDiffViewer` displays before/after diffs, actor attribution, and cooldown countdowns when `detail.reversal_event` is populated. Timeline consumers should ignore `detail.reversal_event` when absent.

## Operational Notes

- Override requests missing lineage now fail with a 422 error. Clients must upgrade before deploying the migration.
- Reversal submissions are rejected while `governance_override_reversal_events.cooldown_expires_at` lies in the future, preventing double reversal during the cooldown window.
- Concurrent reversal attempts on the same override are rejected immediately while a short-lived lock is held (`governance_override_actions.reversal_lock_*` columns). Operators encountering this error should wait for the in-flight reversal to finish or reach out to the actor listed on the lock metadata.
- Governance analytics responses are cached per user/team scope for 30 seconds and automatically invalidated when override actions or governance coaching notes change so operators see fresh SLA deltas without hammering the endpoint.
- The migrations are idempotent; rerunning them will not duplicate lineage rows or reversal events thanks to unique `override_id` constraints.
