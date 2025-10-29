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

## Notifications & Integrations

- Publication events trigger email notifications to repository owners and collaborators using the shared `notify` service.
- Guardrail policies align with custody recovery automation documented in `docs/operations/custody_governance.md` and DNA viewer overlays in `docs/dna_assets.md` to preserve cross-surface narratives.

## Next Steps

- Expand release guardrail evaluation to cross-reference live custody escalation queues via `sample_governance` services.
- Surface differential comparisons between releases and linked DNA asset versions for richer governance storytelling.
