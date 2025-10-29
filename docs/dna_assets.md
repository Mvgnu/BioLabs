# DNA Asset Lifecycle Foundation

## purpose
Capture the initial persistence, versioning, and governance telemetry flows required for the DNA asset lifecycle stack.

## status
experimental

## summary
- Alembic migration `20241010_02_dna_asset_lifecycle` establishes DNA asset, version, annotation, tag, attachment, and guardrail event tables.
- Service module `backend/app/services/dna_assets.py` provides ingestion, versioning, diffing, tagging, and guardrail recording helpers backed by `sequence_toolkit` metrics and configuration profiles.
- DNA asset serialization now bundles kinetics summaries, assembly preset lineage, and planner-aligned guardrail heuristics so operator consoles surface ligation, buffer, and kinetics context without recomputing toolkit stages.
- FastAPI router `backend/app/routes/dna_assets.py` exposes CRUD, diff, and governance endpoints for frontend viewers and governance dashboards.
- Sequence toolkit now offers reusable configuration schemas plus sequence metrics and diff utilities powering both planner and DNA asset flows.
- Pytest coverage (`backend/app/tests/test_dna_assets.py`) exercises creation, versioning, diffing, and guardrail event APIs to anchor future enhancements.

## follow-up considerations
- Expand RBAC beyond creator/admin gating to honour team-level permissions once team ownership semantics are formalised.
- Integrate richer diff visualisations (e.g., alignment contexts) alongside thermodynamic validation when the expanded sequence toolkit profiles mature.
- Surface guardrail events and version telemetry within governance dashboards and SOPs to close the feedback loop for operators.
