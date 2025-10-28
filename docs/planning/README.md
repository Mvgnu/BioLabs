# Planning Dossier

- purpose: organize forward-looking implementation blueprints before execution begins
- status: draft
- updated: 2025-07-05

This directory stores scope notes, dependency maps, and sequencing plans for upcoming iterations (cloning orchestrator, DNA assets, sample governance, collaboration hub, etc.). Each document should reference concrete code locations, outstanding risks, and documentation dependencies so future agents can execute without re-auditing the entire codebase.

## Contents
- `cloning_planner_scope.md`: Multi-step cloning orchestrator blueprint covering backend workflow engine, API routes, frontend wizard, and testing strategy. Backend session persistence (`models.CloningPlannerSession`), service orchestration stubs, FastAPI routes, and pytest coverage have now landed, so remaining tasks focus on Celery pipelines and the frontend wizard experience.
- `dna_asset_model_draft.md`: Proposed schema, service layer, and governance hooks for construct/plasmid asset management.
- `documentation_readiness_check.md`: Checklist mapping future features to the READMEs, SOPs, and guides that must be updated.
