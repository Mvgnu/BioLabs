# DNA Viewer Surface

## purpose
Expose DNA asset annotations, guardrail context, and kinetics summaries using the backend viewer payload contract.

## status
experimental

## architecture
- `hooks/useDNAViewer.ts` hydrates viewer payloads via `/api/dna-assets/{asset_id}/viewer`, caching responses with React Query and supporting optional comparison versions.
- `components/CircularGenome.tsx` and `components/LinearTrack.tsx` provide circular and linear renderers with guardrail-aware styling.
- `components/DNAViewerSummary.tsx` orchestrates the layout, showing kinetics, guardrail states, analytics overlays (codon usage, GC skew, thermodynamic risk), translations, and diff metrics behind a user-controlled analytics toggle.
- Route `dna-viewer/[assetId]/page.tsx` wires the hook and summary component together with comparison controls and empty-state messaging.

## integration notes
- Viewer payloads align with backend schemas in `backend/app/schemas/dna_assets.py`; updates to those contracts should be mirrored in `frontend/app/types.ts`.
- Guardrail badge semantics currently surface `*-review` states; future iterations can extend badge mapping to severity scales and reviewer workflows.
- The viewer expects authenticated API access; ensure tokens are available via existing axios interceptor prior to navigation.
- Importer QA SOPs and analytics overlay expectations are documented in `docs/dna_assets.md` — update this module whenever new backend analytics or provenance fields land.
