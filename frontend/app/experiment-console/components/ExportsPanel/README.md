# ExportsPanel Component

- **File**: `index.tsx`
- **purpose**: render compliance narrative export creation form, bundled evidence selections, and approval controls for experiment executions.
- **inputs**:
  - `executionId` (`string`): current protocol execution identifier used for API calls.
  - `timelineEvents` (`ExecutionEvent[]`): recent events presented as selectable evidence.
- **outputs**: triggers export creation and approval mutations; surfaces persisted history with Markdown previews, attachment summaries, and staged approval interactions.
- **status**: pilot
- **notable behaviours**:
  - Creates exports via `useCreateNarrativeExport`, updating React Query caches and clearing the form after success.
  - Shows up to ten recent timeline events as selectable evidence to bundle with new exports.
  - Renders a stage-by-stage approval ladder, including action history, delegation controls, reset handling, and signature capture for the active stage.
  - Annotates export history entries with persisted guardrail forecasts, including projected delays, tooltips summarising reasons, and disables approvals/delegations when the latest simulation reports a blocked stage.
  - Surfaces guardrail simulation history for each export, highlighting blocked versus clear runs with timestamps so operators can audit forecast evolution inline.
  - Surfaces API errors inline for creation, approval, delegation, and reset flows to keep scientists informed.
  - Displays artifact packaging progress, download links for ready dossiers, and checksum metadata sourced from backend export records.
