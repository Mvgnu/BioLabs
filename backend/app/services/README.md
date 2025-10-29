# Services

This package contains reusable service-layer helpers shared across FastAPI route modules. Each module focuses on cohesive business workflows so API surfaces and background tasks can delegate orchestration logic without duplicating state transitions or RBAC checks.

- `approval_ladders.py` — governance enforcement helpers.
- `cloning_planner.py` — multi-stage cloning planner orchestration covering primer design, restriction analysis, assembly planning, QC ingestion, resumable Celery checkpoints, and guardrail-aware finalization payloads.
- `sequence_toolkit.py` — deterministic primer, restriction, assembly, and QC utilities reused by cloning planner and DNA asset flows.
- `qc_ingestion.py` — chromatogram normalisation, signal-to-noise heuristics, and guardrail breach detection shared across planner QC gating and downstream analytics.

## sequence_toolkit.py

- purpose: shared scientific computation core for DNA planning services
- status: active — enzyme catalog, thermodynamic validation, and multi-strategy assembly engine implemented
- highlights:
  - Curated enzyme metadata loaded from `app/data/enzymes.json` with buffer compatibility, methylation sensitivity, and star activity notes cached for reuse.
  - Dedicated data loaders under `app/data/` surface reaction buffers, enzyme kinetics, ligation profiles, and assembly strategy catalogs with shared caching.
  - Primer design responses surface nearest-neighbor melting temps, GC clamps, and secondary-structure ΔG heuristics for both primers.
  - Restriction digest analysis emits structured schema payloads linking templates to annotated enzyme hits, kinetics presets, buffer context, and guardrail-ready alerts with reusable metadata tags.
  - Assembly simulator now supports Gibson, Golden Gate, HiFi, and homologous recombination heuristics with kinetics modifiers, ligation efficiency scoring, metadata-tagged steps, and machine-readable payload contracts for downstream telemetry.
  - QC evaluation links chromatogram mismatch thresholds with strategy outcomes for governance dashboards.
- `dna_assets.py` — DNA asset persistence, versioning, diffing, and guardrail event helpers powering lifecycle APIs and governance dashboards (now invalidating analytics caches when severe guardrail breaches are recorded).
