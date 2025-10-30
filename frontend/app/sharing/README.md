# Sharing Workspace UI

- purpose: Guardrail-aware DNA repository management experience surfacing releases, approvals, and custody state.
- status: experimental
- depends_on: ../hooks/useSharingWorkspace.ts, ../../backend/app/routes/sharing.py
- related_docs: ../../../docs/sharing/README.md

This directory hosts the Next.js page rendering the guarded DNA sharing workspace. It relies on React Query hooks defined in `frontend/app/hooks/useSharingWorkspace.ts` to fetch repositories, releases, timeline events, and to stream real-time review payloads via Server-Sent Events. Components surface guardrail badges, collaborator management, inline approval shortcuts, release channel orchestration, federated grant workflows, and guardrail diff panels tied to custody guardrails and planner replay checkpoints. The UI now includes:

- Inline federation grant forms that call `POST /api/sharing/federation/links/{link_id}/grants` and approval controls wired to `POST /api/sharing/federation/grants/{grant_id}/decision`.
- Release channel creation and publishing panels capable of attaching active grant IDs so partner distributions remain guardrail-gated.
- Real-time timeline hydration that decorates events with `federation_link`, `federation_grant`, and `release_channel` payloads sourced from the SSE stream.
