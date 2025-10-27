# Governance Preview Simulation

- purpose: document the experiment preview API workflow, simulation parameters, and storage bindings
- status: pilot
- owner: governance squad

## Overview

The `/api/experiments/{execution_id}/preview` endpoint exposes a read-only projection of a governance ladder against a live protocol execution. The route pulls immutable template snapshots, applies optional stage/resource overrides, evaluates gating via `simulation.py`, renders Markdown through `render_preview_narrative`, and records a `template.preview.generated` entry inside `GovernanceTemplateAuditLog` for traceability.

### Stage Mapping Metadata

Each governance template stage can declare associated execution telemetry via `stage_step_indexes` and/or `stage_gate_keys`. The
simulation engine first resolves explicit indexes, then inspects `execution.params.step_requirements` for matching gate keys and
ensures every step is assigned to at least one stage. This produces deterministic blocker groupings and allows preview clients to
highlight which stages are impacted when scientists adjust overrides.

### Request Payload

```json
{
  "workflow_template_snapshot_id": "<snapshot uuid>",
  "resource_overrides": {
    "inventory_item_ids": ["<uuid>"]
  },
  "stage_overrides": [
    {
      "index": 0,
      "sla_hours": 48,
      "assignee_id": "<user uuid>"
    }
  ]
}
```

### Response Snapshot

```json
{
  "execution_id": "<uuid>",
  "snapshot_id": "<uuid>",
  "baseline_snapshot_id": "<uuid>",
  "generated_at": "2024-03-28T17:42:16.430Z",
  "stage_insights": [
    {
      "index": 0,
      "required_role": "scientist",
      "status": "ready",
      "sla_hours": 48,
      "projected_due_at": "2024-03-30T17:42:16.430Z",
      "blockers": [],
      "mapped_step_indexes": [0, 1],
      "gate_keys": ["inventory"],
      "baseline_status": "ready",
      "baseline_sla_hours": 36,
      "baseline_projected_due_at": "2024-03-29T21:42:16.430Z",
      "delta_status": "unchanged",
      "delta_sla_hours": 12,
      "delta_projected_due_minutes": 960,
      "delta_new_blockers": [],
      "delta_resolved_blockers": []
    }
  ],
  "resource_warnings": []
}
```

Front-end clients persist preview history in `localStorage` so scientists can compare multiple simulations before publishing template changes. The updated modal and ladder widget surface simulated vs baseline SLA projections, assignee deltas, blocker diffs, and mapped steps so teams can immediately understand how overrides diverge from production baselines.

## Scenario Workspace API

- purpose: expose persisted preview scenarios scoped to an execution with RBAC enforcement
- status: pilot

### Workspace Retrieval

`GET /api/experiments/{execution_id}/scenarios` returns the full workspace bundle:

```json
{
  "execution": {
    "id": "<execution uuid>",
    "template_id": "<protocol template uuid>",
    "template_name": "Protocol A",
    "template_version": "1",
    "run_by_id": "<user uuid>",
    "status": "in_progress"
  },
  "snapshots": [
    {
      "id": "<snapshot uuid>",
      "template_name": "Baseline Ladder",
      "version": 2,
      "status": "published",
      "captured_at": "2024-04-12T09:21:00Z"
    }
  ],
  "folders": [
    {
      "id": "<folder uuid>",
      "name": "Team Reviews",
      "description": "Shared ladder experiments",
      "visibility": "team",
      "team_id": "<team uuid>",
      "created_at": "2024-04-12T08:30:00Z",
      "updated_at": "2024-04-12T08:30:00Z"
    }
  ],
  "scenarios": [
    {
      "id": "<scenario uuid>",
      "name": "Extended SLA",
      "workflow_template_snapshot_id": "<snapshot uuid>",
      "stage_overrides": [
        { "index": 0, "sla_hours": 72, "assignee_id": "<scientist uuid>" }
      ],
      "resource_overrides": {
        "inventory_item_ids": ["<inventory uuid>"]
      },
      "folder_id": "<folder uuid>",
      "is_shared": true,
      "shared_team_ids": ["<team uuid>", "<partner team uuid>"],
      "expires_at": "2024-05-01T00:00:00Z",
      "timeline_event_id": "<timeline event uuid>",
      "created_at": "2024-04-12T10:00:00Z",
      "updated_at": "2024-04-12T10:05:00Z"
    }
  ]
}
```

Only administrators, the execution owner, or team members attached to the protocol template are authorised to access the workspace.

### Scenario Lifecycle

- `POST /api/experiments/{execution_id}/scenario-folders` creates collaboration folders with visibility controls; `PATCH /api/experiments/{execution_id}/scenario-folders/{folder_id}` renames or adjusts visibility as scenarios evolve.
- `POST /api/experiments/{execution_id}/scenarios` persists a new scenario bound to the execution, normalising UUIDs, binding optional folders, shared team lists, expiration timestamps, and timeline anchors before logging a `scenario.saved` execution event.
- `PUT /api/experiments/{execution_id}/scenarios/{scenario_id}` updates metadata, overrides, sharing controls, owner transfers, or snapshot bindings (owner/admin only) while emitting `scenario.updated` with folder and expiry metadata.
- `POST /api/experiments/{execution_id}/scenarios/{scenario_id}/clone` duplicates an existing scenario for rapid iteration, recording a `scenario.cloned` timeline event.
- `DELETE /api/experiments/{execution_id}/scenarios/{scenario_id}` removes the record and emits `scenario.deleted` for auditability.

The frontend modal (`ScenarioSummary` + updated `PreviewModal`) consumes these APIs via React Query, enabling scientists to iterate on overrides, organise scenarios inside execution-specific folders, toggle shared visibility by team, schedule expiration pruning, deep-link discussions to timeline events, and run previews without manually copying UUIDs.
