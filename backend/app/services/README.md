# Services

This package contains reusable service-layer helpers shared across FastAPI route modules. Each module focuses on cohesive business workflows so API surfaces and background tasks can delegate orchestration logic without duplicating state transitions or RBAC checks.

- `approval_ladders.py` — governance enforcement helpers.
- `cloning_planner.py` — multi-stage cloning planner orchestration covering primer design, restriction analysis, assembly planning, QC ingestion, resumable Celery checkpoints, guardrail-aware finalization payloads, **durable stage history records persisted to `cloning_planner_stage_records`, QC artifact lineage, and Redis-backed progress events for streaming UIs**.
- `sequence_toolkit.py` — deterministic primer, restriction, assembly, and QC utilities reused by cloning planner and DNA asset flows.
- `qc_ingestion.py` — chromatogram normalisation, signal-to-noise heuristics, guardrail breach detection shared across planner QC gating and downstream analytics, **with durable chromatogram storage, reviewer decisions, and linkage to planner stage history**.
- `sample_governance.py` — freezer topology and custody orchestration providing guardrail-aware ledger creation, occupancy analytics, SLA-tracked escalation queues, automated notification dispatch, freezer fault modeling, and protocol execution linkage so custody escalations and ledger events annotate experiment lifecycles in real time **with acknowledged escalations still enforcing guardrail gating and protocol snapshots filtered by team, template, or execution identifiers for downstream RBAC alignment**.

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
- `dna_assets.py` — DNA asset persistence, versioning, diffing, viewer payload generation, and guardrail event helpers powering lifecycle APIs and governance dashboards (now invalidating analytics caches when severe guardrail breaches are recorded and exposing `build_viewer_payload` for UI overlays). The viewer analytics now emit translation frame utilisation summaries, codon adaptation index heuristics, motif hotspot overlays, and mitigation guidance for thermodynamic guardrails.
- `importers/` — adapter suite transforming GenBank, SBOL, and SnapGene uploads into `DNAImportResult` payloads complete with provenance attachments and normalised annotations before invoking `dna_assets.create_asset`. GenBank parsing now sorts compound joins, preserves complementary regulatory spans, and expands provenance tags beyond gene/product into experiment, function, and bound moiety qualifiers.
