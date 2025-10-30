# Guarded DNA Sharing Workspace

- purpose: Outline governance-aware repository sharing workflows that link planner guardrails, custody recovery, and release approvals.
- status: experimental
- related_docs: docs/planning/cloning_planner_scope.md, docs/operations/custody_governance.md, docs/dna_assets.md

## Overview

The guarded DNA sharing workspace unifies planner checkpoints, custody guardrails, and DNA asset governance into a repository-centric experience. Each repository maintains a guardrail policy describing required approvals, custody clearance expectations, and mitigation playbooks.

## Repository Lifecycle

1. **Repository Creation** – Operators configure guardrail policies when registering a repository, including approval thresholds, custody clearance requirements, and mitigation playbooks.
2. **Collaborator Onboarding** – Collaborators assume viewer, contributor, maintainer, or owner roles. Maintainers can queue releases and satisfy guardrail approvals.
3. **Release Authoring** – Release payloads reference planner session IDs and embed guardrail snapshots summarizing custody and mitigation status. Releases blocked by custody guardrails remain in `requires_mitigation` until the underlying holds resolve.
4. **Guardrail Approvals** – Maintainers and owners file approvals with guardrail flags and notes. Once the approval threshold is met, releases publish automatically, emitting notifications to stakeholders.
5. **Timeline Narratives** – Each action records a timeline event, capturing policy updates, collaborator changes, release transitions, and approval outcomes for downstream governance surfaces.

## Federation & Release Channels

- **Federated Links** – Repositories can now register cross-organization federation links capturing guardrail contracts, trust state, and attestation history. The `dna_repository_federation_links` and `dna_repository_federation_attestations` tables enforce provenance, with timeline events surfacing contract updates in real time.
- **Release Channels** – Release channels provide versioned placements tailored to partner or regional audiences. Guardrail attestation payloads and mitigation digests accompany every channel version, ensuring downstream custodians inherit the correct compliance context.

## Collaborative Review Stream

- The `/api/sharing/repositories/{id}/reviews/stream` SSE endpoint delivers a live stream of release activity, attestation updates, and channel publications. The Next.js workspace consumes this stream to present inline guardrail diffs, lifecycle snapshots, and replay checkpoints without requiring manual refreshes.
- Timeline payloads now embed `lifecycle_snapshot`, `mitigation_history`, and `replay_checkpoint` metadata, aligning review conversations with planner replay narratives.

## Governance Playbook for Inter-Org Sharing

1. **Establish Federation Contract** – Configure link metadata outlining guardrail expectations, permissible permissions, and attestation cadence. Record countersignatures using the `record_federation_attestation` workflow.
2. **Curate Release Channels** – Map releases to partner-facing channels with scoped guardrail profiles. Every placement must include provenance snapshots, mitigation digests, and replay checkpoints to satisfy audit requirements.
3. **Stream Reviews** – Use the live collaboration hub to validate guardrail diffs, confirm mitigation history, and reconcile planner checkpoints before approvals.
4. **Archive Evidence** – Export attestation payloads and timeline snapshots into custody governance storage for long-term compliance retention.

## Notifications & Integrations

- Publication events trigger email notifications to repository owners and collaborators using the shared `notify` service.
- Guardrail policies align with custody recovery automation documented in `docs/operations/custody_governance.md` and DNA viewer overlays in `docs/dna_assets.md` to preserve cross-surface narratives.

## Next Steps

- Expand release guardrail evaluation to cross-reference live custody escalation queues via `sample_governance` services.
- Surface differential comparisons between releases and linked DNA asset versions for richer governance storytelling.
- Pilot federated repository exchanges with partner guardrail attestations and release channels tailored for regional residency commitments.
