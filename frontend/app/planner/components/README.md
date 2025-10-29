# Planner Components

This directory hosts client-side components for the cloning planner experience.

- `PlannerWizard.tsx` – orchestrates the primary planner workflow UI, integrating guardrail summaries, stage controls, deterministic resume tokens, `recovery_bundle` readiness signals, recovery actions, and toolkit preset selections resolved via `useSequenceToolkitPresets`.
- `PlannerTimeline.tsx` – renders the branch-aware timeline scrubber that replays SSE events, guardrail transitions, custody checkpoints, mitigation hints, branch comparison badges, curated recovery bundle summaries, and custody `drill_summaries` while exposing per-checkpoint resume actions.

Both components consume data from `useCloningPlanner` and surface guardrail-aware status indicators aligned with backend orchestration metadata.
