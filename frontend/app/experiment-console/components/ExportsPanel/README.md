# ExportsPanel Component

- **File**: `index.tsx`
- **purpose**: render compliance narrative export creation form, bundled evidence selections, and approval controls for experiment executions.
- **inputs**:
  - `executionId` (`string`): current protocol execution identifier used for API calls.
  - `timelineEvents` (`ExecutionEvent[]`): recent events presented as selectable evidence.
- **outputs**: triggers export creation and approval mutations; surfaces persisted history with Markdown previews, attachment summaries, and signature capture.
- **status**: pilot
- **notable behaviours**:
  - Creates exports via `useCreateNarrativeExport`, updating React Query caches and clearing the form after success.
  - Shows up to ten recent timeline events as selectable evidence to bundle with new exports.
  - Provides inline approval form and disables decisions once an export is no longer pending.
  - Surfaces API errors inline for both export creation and approval flows to keep scientists informed.
  - Displays artifact packaging progress, download links for ready dossiers, and checksum metadata sourced from backend export records.
