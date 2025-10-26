# Timeline Component

- **File**: `index.tsx`
- **Purpose**: renders the execution timeline stream with virtualised rows, filter controls, and annotation affordances for operators.
- **Key behaviours**:
  - Consumes paginated data from `useExecutionTimeline`, requesting additional pages as the user scrolls near the end of the buffer.
  - Provides event-type toggles that delegate filter changes back to the page so new server-side queries are issued.
  - Supports inline annotations stored client-side via callbacks, allowing future wiring to persistence services without changing the UI contract.
- **Rendering notes**:
  - Uses a lightweight manual virtualisation strategy (`ITEM_HEIGHT` + overscan) to avoid introducing third-party dependencies.
  - The component defends against environments without `ResizeObserver` by falling back to the container height on mount.

Update this document when adding new controls (e.g., annotation persistence, export buttons) or altering the virtualisation heuristics.
