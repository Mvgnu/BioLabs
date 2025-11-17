# Compliance Dashboard

- purpose: visualize compliance records, residency summaries, and guardrail annotations for operational teams
- status: active
- depends_on: `frontend/app/hooks/useCompliance.ts`, `/api/compliance/records`, `/api/compliance/summary`, `/api/compliance/organizations`
- inputs: React Query data sets for organizations, records, and summary counts; form state for new compliance records
- outputs: guardrail-aware record creation mutations and UI summaries showing residency posture

The compliance dashboard lets operators log guardrail evaluations tied to residency policies and inspect existing records. It exposes:

- Organization selector sourced from enterprise compliance administration
- Record logging form that captures record type, data domain, region overrides, and notes
- Summary tiles aggregated by status to highlight restricted or pending actions
- Detailed record cards listing guardrail flags, retention periods, and quick approval controls

Use this page to provide human-readable context for residency enforcement decisions surfaced by the planner, DNA asset workflows, and admin UI.
