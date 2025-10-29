# Governance Components

- purpose: Provide reusable building blocks for the governance admin workspace UI.
- scope: Components under this directory power the workflow template library, editor, and ladder builder experiences.
- status: experimental
- owner: governance squad

## Components

- `TemplateLibrary`: Grid list of templates with metadata cards.
- `TemplateEditor`: Authoring surface tied to the ladder builder and assignment manager.
- `LadderBuilder`: React Flow powered stage designer with palette + inspector.
- `LadderSimulationWidget`: Scientist-facing sandbox that calls the preview API using draft ladder data for scenario comparisons and surfaces persisted guardrail simulations beside ad-hoc previews.
- `OverdueDashboard`: Operator dashboard summarising overdue ladder analytics with escalation affordances powered by governance meta payloads.
- `GuardrailHealthDashboard`: Surfaces sanitized packaging queue telemetry, blocked export counts, and pending stage context so governance operators can monitor guardrail enforcement health without querying raw events.
- `CustodyFreezerMap`: Visualises freezer units and compartment occupancy with guardrail badges to drive custody oversight dashboards.
- `CustodyLedgerPanel`: Renders custody ledger timelines with lineage cues and guardrail annotations for audit triage.
- `CustodyEscalationPanel`: Aggregates custody escalation queues, SLA timers, freezer fault telemetry, and protocol execution context with acknowledge, notify, and resolve affordances aligned with governance RBAC rules.

Each component embeds machine-readable metadata comments to satisfy Biolab documentation standards.
