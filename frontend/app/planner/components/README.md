# Planner Components

This directory hosts client-side components for the cloning planner experience.

- `PlannerWizard.tsx` – orchestrates the primary planner workflow UI, integrating guardrail summaries, stage controls, and recovery actions.
- `PlannerTimeline.tsx` – renders the branch-aware timeline scrubber that replays SSE events, guardrail transitions, and custody checkpoints for operator review.

Both components consume data from `useCloningPlanner` and surface guardrail-aware status indicators aligned with backend orchestration metadata.
