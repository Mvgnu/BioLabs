# Analytics Hooks

- purpose: provide reusable React hooks for governance analytics payloads
- scope: hooks consuming `/api/governance/analytics` responses that expose derived reviewer cadence metadata
- status: pilot

## Hooks

- `useReviewerCadence.ts` – fetches reviewer cadence summaries and derives band counts plus streak alert subsets for composable UI layers.
