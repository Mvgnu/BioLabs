# Services

This package contains reusable service-layer helpers shared across FastAPI route modules. Each module focuses on cohesive business workflows so API surfaces and background tasks can delegate orchestration logic without duplicating state transitions or RBAC checks.

- `approval_ladders.py` — governance enforcement helpers.
- `cloning_planner.py` — multi-stage cloning planner orchestration covering primer design, restriction analysis, assembly planning, and guardrail-aware finalization payloads.
- `sequence_toolkit.py` — deterministic primer, restriction, assembly, and QC utilities reused by cloning planner and DNA asset flows.
- `dna_assets.py` — DNA asset persistence, versioning, diffing, and guardrail event helpers powering lifecycle APIs and governance dashboards.
