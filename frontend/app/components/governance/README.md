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

Each component embeds machine-readable metadata comments to satisfy Biolab documentation standards.
