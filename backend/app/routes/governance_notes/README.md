# Governance Coaching Notes Routes

## Purpose
- Persist and expose reviewer coaching context alongside governance overrides.
- Provide threaded replies, moderation state toggles, and metadata surfaces for UI collaboration workflows.

## Endpoints
- `GET /api/governance/overrides/{override_id}/coaching-notes`
  - Returns ordered note threads for an override with reply counts and actor summaries.
- `POST /api/governance/overrides/{override_id}/coaching-notes`
  - Creates a new note or threaded reply. Automatically seeds `thread_root_id` and inherits execution/baseline lineage when omitted.
- `PATCH /api/governance/coaching-notes/{note_id}`
  - Updates body content, moderation states, and metadata with edit timestamping.

## RBAC Notes
- Admins bypass all checks.
- Override actors, target reviewers, and execution owners receive implicit access.
- Team membership is resolved via associated baseline or template team identifiers before granting broader visibility.

## Metadata Contract
- Responses emit `metadata`, `reply_count`, and `moderation_state` fields to support optimistic UI updates.
- Machine-readable comments in `models.py` and schemas document lineage dependencies for downstream automation.
