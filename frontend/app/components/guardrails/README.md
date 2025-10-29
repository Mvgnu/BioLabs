# Guardrail UI Components

## purpose
Reusable visual primitives for surfacing guardrail states, escalations, reviewer handoffs, and QC decision loops across planner, governance, and viewer surfaces.

## status
experimental

## components
- `GuardrailBadge` — renders a status badge with severity-aware styling and optional metadata tags.
- `GuardrailEscalationPrompt` — highlights actionable guardrail escalations with acknowledgement affordances.
- `GuardrailReviewerHandoff` — summarises reviewer context, contact channels, and handoff notes.
- `GuardrailQCDecisionLoop` — lists QC artifacts, breach metrics, and reviewer decisions to guide approval loops.

## integration notes
- Components expect guardrail payloads shaped like backend `guardrail_state` snapshots and cloning planner QC artifacts.
- Use shared Tailwind tokens for consistent severity theming: green (`ok`), amber (`review`), rose (`breach`/`blocked`).
- Surfaces should wire callbacks to escalate, notify reviewers, or acknowledge QC loops where workflows permit.
