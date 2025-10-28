# Reflection – 2025-07-09 – Telemetry Contract Parity

- purpose: capture lessons from enforcing sanitised packaging telemetry across surfaces
- status: draft
- related_docs: docs/governance/export_enforcement_audit.md, docs/governance/operator_sop.md, progress.md

## Wins
- Centralising the payload spec and running it through a sanitiser eliminated drift between API, CLI, and worker emissions, so dashboards and operators can trust a single queue contract.
- Governance pytest coverage on the sanitiser caught a latent bug where CLI context carried extra keys, proving the shared helper prevents future regressions.

## Challenges
- Balancing context richness with minimal payloads required iterating on which guardrail fields were essential for operators, especially when reconciling SLA monitor alerts.
- Coordinating documentation updates across audit logs, SOPs, and progress tracking took deliberate sequencing to keep the living documentation mandate intact.

## Next Steps
- Extend telemetry sanitisation to future cloning planner and DNA asset workflows as they adopt queue-based guardrails.
- Backfill dashboard consumers with automated checks that fail builds if new event fields appear without an updated spec.
