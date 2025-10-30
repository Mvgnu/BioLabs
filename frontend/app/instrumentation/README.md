# Instrumentation Digital Twin UI

This directory hosts the instrumentation digital twin dashboard rendered at `/instrumentation`. The page combines instrument profiles, guardrail context, and telemetry timelines, and exposes deterministic simulation controls to validate orchestration flows before issuing commands to physical hardware.

## Components

- `page.tsx` renders the primary dashboard layout with instrument selection, run control, and telemetry timeline cards.

## Data Dependencies

- Hooks from `../hooks/useInstrumentation` supply instrument profiles, run envelopes, and simulation mutations.
- API endpoints originate from `backend/app/routes/instrumentation.py`.

## Status

- **Status**: Pilot. The UI focuses on foundational telemetry visualization and will expand with charting and collaborative review overlays in future iterations.
