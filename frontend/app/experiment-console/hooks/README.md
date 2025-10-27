# Experiment Console Hooks

- purpose: collate experiment console-specific hooks that orchestrate governance previews and override UX
- status: pilot

## Hooks

- `useGovernanceRecommendations.ts` – fetches `/api/governance/recommendations/override`, exposing grouped recommendations, priority buckets, and cached metadata for the preview modal.
