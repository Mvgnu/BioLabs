# Services

This package contains reusable service-layer helpers shared across FastAPI route modules. Each module focuses on cohesive business workflows so API surfaces and background tasks can delegate orchestration logic without duplicating state transitions or RBAC checks.

- `approval_ladders.py` — governance enforcement helpers.
- `cloning_planner.py` — multi-stage cloning planner orchestration covering primer design, restriction analysis, assembly planning, and guardrail-aware finalization payloads.
- `sequence_toolkit.py` — deterministic primer, restriction, assembly, and QC utilities reused by cloning planner and DNA asset flows.

## sequence_toolkit.py

- purpose: shared scientific computation core for DNA planning services
- status: active — enzyme catalog + thermodynamic validation implemented
- highlights:
  - Curated enzyme metadata loaded from `app/data/enzymes.json` with buffer compatibility, methylation sensitivity, and star activity notes cached for reuse.
  - Primer design responses now surface nearest-neighbor melting temps, GC clamps, and secondary-structure ΔG heuristics for both primers.
  - Restriction digest analysis emits structured schema payloads linking templates to annotated enzyme hits and buffer warnings.
  - Assembly/QC simulators output typed payloads compatible with governance rollups and frontend integrations.
- `dna_assets.py` — DNA asset persistence, versioning, diffing, and guardrail event helpers powering lifecycle APIs and governance dashboards.
