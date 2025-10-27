# Governance CLI

## Purpose
- provide: governance lifecycle utilities for administrators
- status: pilot
- depends_on: backend.app.cli.migrate_templates

## Commands
- `python -m backend.app.cli migrate-exports` — bind legacy narrative exports to published template snapshots.
- Add `--dry-run` to inspect affected exports without persisting changes.

## Logging
- anomalies and migration issues are appended to `problems/governance_migration.log` for review.
