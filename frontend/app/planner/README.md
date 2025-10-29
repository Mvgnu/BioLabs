# Cloning Planner Wizard

## purpose
Expose a multi-stage cloning planner console that mirrors backend orchestration, subscribes to SSE guardrail progress, and guides operators through primer, restriction, assembly, and QC checkpoints.

## status
experimental

## architecture
- `page.tsx` renders the intake form for bootstrapping planner sessions and redirects into the wizard surface.
- `components/PlannerWizard.tsx` binds the `useCloningPlanner` hook with shared guardrail components, stage stepper UI, and QC artifact previews.
- `[sessionId]/page.tsx` loads the client wizard for a specific session, wiring resumable state, SSE event stream, and retry affordances.

## integration notes
- Planner actions delegate to `/api/cloning-planner` endpoints via the shared `api/cloningPlanner.ts` client.
- SSE progress streams are sourced from `/api/cloning-planner/sessions/{sessionId}/events` using the `useCloningPlanner` hook.
- Guardrail components from `app/components/guardrails` provide consistent escalation prompts and QC loops across planner, governance, and DNA viewer surfaces.
- Custody guardrail gates are surfaced through the new `guardrail_gate` payload on sessions and SSE events. When `active` is `true`, the wizard disables stage controls, shows custody badges, and emits explanatory copy listing the gate reasons (e.g., `custody_status:halted`, `qc_backpressure`).
- Governance dashboards can query `GET /api/cloning-planner/sessions/{sessionId}/guardrails` to render the same custody overlays surfaced inside the wizard. The hook invalidates the session query whenever SSE events arrive so the UI banner and custody badge stay aligned with the latest guardrail backpressure state.
