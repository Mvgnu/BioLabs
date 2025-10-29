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
- Importer suite under `backend/app/services/importers/` normalises GenBank, SBOL, and SnapGene uploads into `DNAImportResult` payloads before invoking `dna_assets.create_asset`, preserving topology, annotations, source metadata, provenance tags, and original attachments for governance provenance. The GenBank adapter now sorts compound joins, propagates regulatory qualifiers, and extends provenance tags to include experiment, function, and bound-molecule descriptors.
- Viewer payload builder `dna_assets.build_viewer_payload` assembles feature tracks, guardrail overlays, translated CDS frames, kinetics summaries, analytics overlays (codon usage, GC skew, thermodynamic risk), and optional version diffs for frontend consumption using the `DNAViewerPayload` schema family.
- Viewer analytics now layer translation frame utilisation, codon adaptation index, and motif hotspot overlays alongside refreshed thermodynamic mitigation guidance to support governance consumers.
- Viewer payloads now embed governance-first context including lineage breadcrumbs, guardrail event history, regulatory feature density heuristics, and surfaced mitigation playbooks that align with custody dashboards.
- Pytest coverage (`backend/app/tests/test_dna_assets.py`, `backend/app/tests/test_dna_importers.py`) exercises asset lifecycle APIs, importer fidelity, and viewer payload construction using representative fixture files stored under `backend/app/tests/data/importers/`.

## importer workflows

- Uploads flow through `services/importers/{genbank,sbol,snapgene}.py` which emit canonical `DNAImportResult` objects encapsulating sequence topology, annotations, provenance, tags, and attachments (including the original upload under a media-type specific wrapper).
- `DNAImportResult.to_asset_payload` hydrates a `DNAAssetCreate` schema, ensuring importer metadata propagates into persistent asset records while normalising qualifiers, multi-segment coordinates, and provenance tags for viewer contracts.
- Representative fixtures (`backend/app/tests/data/importers/`) cover plasmid, SBOL XML, SnapGene JSON/binary, and multi-segment CDS scenarios validating annotations, topology, provenance, and attachment fidelity via pytest fixtures. New GenBank fixture `segmented_regulatory.gb` exercises multi-segment CDS joins, complementary regulatory spans, and provenance qualifier flattening.

## viewer payload contract

- `dna_assets.build_viewer_payload` returns `DNAViewerPayload` combining latest asset metadata, sequence, guardrail heuristics, kinetics, analytics overlays, translations, and diff summaries for optional comparison.
- Feature tracks embed guardrail badges derived from `guardrail_heuristics` so frontend components (e.g., `GuardrailBadge`, `LinearTrack`) surface planner-aligned alerts without recomputation.
- Frontend surfaces at `/dna-viewer/[assetId]` and the cloning planner wizard reuse guardrail primitives to present consistent escalation and QC loops sourced directly from the viewer payload and planner SSE events.

## importer QA SOPs

1. Validate every new importer scenario with pytest fixtures under `backend/app/tests/data/importers/`, ensuring multi-segment CDS joins, regulatory qualifiers, and provenance notes are captured via `segments` and `provenance_tags` fields.
2. Confirm attachments persist original file bytes and metadata fingerprints to preserve audit trails.
3. Inspect resulting `DNAImportResult.to_asset_payload()` objects to verify topology, guardrail tags, and provenance labels prior to database insertion.
4. When regressions are identified, update fixtures to reproduce the edge case and extend assertions for provenance or analytics coverage.

## viewer analytics overlays

- Backend analytics enrich the viewer payload with `codon_usage`, `gc_skew`, and `thermodynamic_risk` overlays sourced from importer heuristics and guardrail summaries, plus translation frame utilisation, codon adaptation index, and motif hotspot overlays.
- Frontend components toggle these overlays via the analytics panel to avoid overwhelming default views while keeping advanced metrics a click away for scientists and governance reviewers.
- Thermodynamic risk overlays aggregate homopolymer runs, GC hotspots, primer ΔTm span, guardrail warning counts, and mitigation guidance; the overall state should align with guardrail escalation cues.

## follow-up considerations
- Expand RBAC beyond creator/admin gating to honour team-level permissions once team ownership semantics are formalised.
- Integrate richer diff visualisations (e.g., alignment contexts) alongside thermodynamic validation when the expanded sequence toolkit profiles mature.
- Surface guardrail events and version telemetry within governance dashboards and SOPs to close the feedback loop for operators.
