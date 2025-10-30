# Sharing Workspace UI

- purpose: Guardrail-aware DNA repository management experience surfacing releases, approvals, and custody state.
- status: experimental
- depends_on: ../hooks/useSharingWorkspace.ts, ../../backend/app/routes/sharing.py
- related_docs: ../../../docs/sharing/README.md

This directory hosts the Next.js page rendering the guarded DNA sharing workspace. It relies on React Query hooks defined in `frontend/app/hooks/useSharingWorkspace.ts` to fetch repositories, releases, timeline events, and to stream real-time review payloads via Server-Sent Events. Components surface guardrail badges, collaborator management, inline approval shortcuts, release channel summaries, and guardrail diff panels tied to custody guardrails and planner replay checkpoints.
