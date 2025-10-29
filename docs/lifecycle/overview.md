# Lifecycle Narrative Aggregation Service

The lifecycle narrative aggregation service stitches together planner stage
records, DNA guardrail events, custody logs, and guarded repository timelines so
operators can see a unified lifecycle summary for governed artefacts.

## Scope Selectors

The `/api/lifecycle/timeline` endpoint accepts any combination of the
following identifiers to scope aggregation:

- `planner_session_id`
- `dna_asset_id` or `dna_asset_version_id`
- `custody_log_inventory_item_id`
- `protocol_execution_id`
- `repository_id`

At least one identifier must be supplied. The service validates access rights
based on the authenticated operator.

## Response Contract

Responses include:

- `summary`: aggregate metrics such as total events, open escalations, active
  guardrails, custody state, and context chips for UI badges.
- `entries`: ordered lifecycle timeline entries annotated with guardrail flags,
  checkpoint metadata, and source labels (`planner`, `custody`, `dna_asset`,
  `repository`).

Frontend consumers use the `LifecycleSummaryPanel` to render summary metrics,
context chips, guardrail severity badges, and timeline items with timestamp and
checkpoint details.

