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
