# Primer and Restriction Presets

The cloning planner exposes a curated catalog of Sequence Toolkit presets that
align primer design, restriction analysis, and assembly scoring.

## Available Presets

- **multiplex** – balances tm windows for Golden Gate and multiplex PCR workflows,
  emphasising Type IIS digestion and overhang diversity.
- **qpcr** – narrows amplicon length and tm spread for qPCR validation and assay
  verification guardrails.
- **high_gc** – increases clamp requirements and salt concentrations to stabilise
  GC-rich templates when planning Gibson assemblies.

Each preset injects overrides for primer design, restriction digest heuristics,
and assembly simulation models. Preset metadata is surfaced on the planner UI in
the guardrail overview, and propagated through the `toolkit` guardrail snapshot
that downstream governance and DNA viewer surfaces can consume.

## Guardrail Metrics

Preset selection now enriches guardrail telemetry with:

- **Multiplex compatibility** – tm window and cross-dimer flags emitted by
  `design_primers`, providing quick review of multiplex risk.
- **Restriction strategy scores** – double digest and Golden Gate compatibility
  heuristics surfaced via `analyze_restriction_digest`.
- **Toolkit snapshots** – per-stage profiles recorded alongside guardrail state
  so resume flows and downstream analytics retain preset provenance.

Refer to the planner README for UI controls and to
`docs/operations/custody_governance.md` for governance integration guidance.
