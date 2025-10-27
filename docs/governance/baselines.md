# Baseline Governance Lifecycle

Baseline governance codifies how preview insights graduate into organization-wide controls. The lifecycle formalizes submission, review, publication, and rollback activities so leadership can ratify ladder changes with auditable state transitions.

## Lifecycle States

| State | Description |
| --- | --- |
| `submitted` | Scientist-proposed baseline awaiting reviewer action. |
| `approved` | Reviewer has endorsed the baseline and it is ready for publication. |
| `rejected` | Reviewers declined the submission. Authors may resubmit after revisions. |
| `published` | Baseline is the active standard for the associated protocol template. |
| `rolled_back` | Baseline has been deactivated in favor of an earlier version. |

Every transition persists to `governance_baseline_events` with actor identifiers, notes, and structured metadata for downstream auditing.

## API Surface

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/governance/baselines/submissions` | Register a new baseline submission tied to a protocol execution. |
| `GET` | `/api/governance/baselines` | Enumerate accessible baselines with optional `execution_id` or `template_id` filters. |
| `GET` | `/api/governance/baselines/{baseline_id}` | Fetch lifecycle details and event history for a single baseline. |
| `POST` | `/api/governance/baselines/{baseline_id}/review` | Approve or reject a submission. Restricted to assigned reviewers or admins. |
| `POST` | `/api/governance/baselines/{baseline_id}/publish` | Publish an approved baseline and retire prior versions. |
| `POST` | `/api/governance/baselines/{baseline_id}/rollback` | Roll back a published baseline (admin only) with optional restoration of a prior version. |

All routes require authentication. RBAC is enforced via execution workspace membership and reviewer assignments.

## Reviewer Workflow

1. **Submission** – Scientists specify labels, reviewer assignments, and context while anchoring the baseline to an execution.
2. **Review** – Assigned reviewers receive visibility regardless of team membership. Approvals capture notes for downstream reporting.
3. **Publish** – Approved baselines can be published by reviewers or administrators. Publishing assigns an incremental `version_number` per protocol template and flips the `is_current` flag while retiring previous versions.
4. **Rollback** – Administrators can roll back an active baseline, optionally reinstating a prior version. Both actions emit audit events.

## Experiment Console Workflow

The experiment console exposes a "Baseline governance" panel that mirrors the lifecycle API:

- **Submission form** – Scientists draft proposals directly within an execution workspace. The form captures a name, narrative context, reviewer identifiers, and lifecycle labels. RBAC gates submission: controls remain visible for context but are disabled unless the viewer is an execution owner or administrator.
- **Reviewer queue** – Active baselines appear with status badges, assignments, and quick actions. Reviewers can approve or reject submissions, while administrators (or approved reviewers) can publish or roll back. Actions prompt for optional notes which are persisted via `/api/governance/baselines/*` endpoints.
- **Event timeline** – A live timeline reflects the `governance_baseline_events` audit trail. Each transition surfaces timestamps, actor notes, and structured metadata to support investigations.

React Query hooks in `useExperimentConsole` perform optimistic updates so queue state remains responsive. All controls respect RBAC checks and fall back to view-only mode when permissions are insufficient.

## Data Model Highlights

- `governance_baseline_versions` stores lifecycle metadata, reviewer assignments, and publication history.
- `governance_baseline_events` logs structured transitions for each baseline.
- Every baseline references the originating `protocol_executions` record to guarantee execution-level RBAC alignment.

## Analytics Signals

Baseline lifecycle telemetry now feeds the governance analytics service so operators can correlate preview health with publishing discipline:

- **Approval latency (minutes)** – average time from submission to review for the baselines associated with a previewed execution. Long latencies indicate reviewer bottlenecks or staffing gaps.
- **Publication cadence (days)** – mean interval between published baseline versions for the same template, exposing stagnation or excessive churn.
- **Baseline coverage** – total baseline versions observed for the aggregated previews, surfaced in analytics totals to highlight high-change areas.
- **Rollback count** – number of rolled-back baselines tied to the preview set, signaling rollback risk when compared against blocker heatmaps.

These metrics surface within the experiment console analytics panel via the "Baseline Lifecycle Pulse" card. They reuse the `/api/governance/analytics` payloads, avoiding duplicate baseline queries and keeping the lifecycle panel as the single source of truth for version details. Guardrails follow the same RBAC policies defined earlier—only executions and baselines accessible to the viewer contribute to analytics. When extending analytics, document additional KPIs here with definitions, rationale, and any privacy limitations.

Refer to `backend/alembic/versions/a7d3e0c5f1ab_governance_baseline_lifecycle.py` for the schema definition and to `backend/app/routes/governance_baselines.py` for route logic.
