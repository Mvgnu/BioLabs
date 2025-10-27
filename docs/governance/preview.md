# Governance Preview Simulation

- purpose: document the experiment preview API workflow, simulation parameters, and storage bindings
- status: pilot
- owner: governance squad

## Overview

The `/api/experiments/{execution_id}/preview` endpoint exposes a read-only projection of a governance ladder against a live protocol execution. The route pulls immutable template snapshots, applies optional stage/resource overrides, evaluates gating via `simulation.py`, renders Markdown through `render_preview_narrative`, and records a `template.preview.generated` entry inside `GovernanceTemplateAuditLog` for traceability.

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
  "generated_at": "2024-03-28T17:42:16.430Z",
  "stage_insights": [
    {
      "index": 0,
      "required_role": "scientist",
      "status": "ready",
      "sla_hours": 48,
      "projected_due_at": "2024-03-30T17:42:16.430Z",
      "blockers": []
    }
  ],
  "resource_warnings": []
}
```

Front-end clients persist preview history in `localStorage` so scientists can compare multiple simulations before publishing template changes.
