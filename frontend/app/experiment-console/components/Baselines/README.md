# Baselines Components

These components power the baseline governance console embedded within the experiment execution workspace.

## Files

- `BaselinesPanel.tsx` – Top-level container that orchestrates submission, reviewer queue, and timeline panes. Wires React Query
  hooks for optimistic lifecycle updates.
- `BaselineSubmissionForm.tsx` – Scientist-facing form for drafting baseline proposals with reviewer assignments and metadata
  labels.
- `BaselineReviewerQueue.tsx` – Reviewer surface that exposes approve/reject, publish, and rollback actions with RBAC gating.
- `BaselineTimeline.tsx` – Timeline renderer for lifecycle events mirroring the backend schema.
- `index.ts` – Convenience export for `BaselinesPanel`.

## Usage

`BaselinesPanel` expects the execution id, template metadata, and RBAC context. It handles optimistic updates by delegating to
the React Query hooks defined in `useExperimentConsole`.
