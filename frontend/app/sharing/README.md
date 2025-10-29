# Sharing Workspace UI

- purpose: Guardrail-aware DNA repository management experience surfacing releases, approvals, and custody state.
- status: experimental
- depends_on: ../hooks/useSharingWorkspace.ts, ../../backend/app/routes/sharing.py
- related_docs: ../../../docs/sharing/README.md

This directory hosts the Next.js page rendering the guarded DNA sharing workspace. It relies on React Query hooks defined in `frontend/app/hooks/useSharingWorkspace.ts` to fetch repositories, releases, and timeline events. Components surface guardrail badges, collaborator management, and inline approval shortcuts aligned with backend guardrail policy enforcement.
