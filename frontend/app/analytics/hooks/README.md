# Analytics Hooks

- purpose: provide reusable React hooks for governance analytics payloads
- scope: hooks consuming `/api/governance/analytics` responses that expose derived reviewer cadence metadata
- status: pilot

## Hooks

- `useReviewerCadence.ts` – fetches the lean `view=reviewer` payload, exposing reviewer cadence summaries, load band counts, streak alerts, and aggregate latency guardrails for composable UI layers.
