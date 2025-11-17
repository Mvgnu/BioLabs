# Enterprise Data Residency & Compliance Controls

## Overview
The enterprise compliance stack introduces organization-scoped residency policies, encryption posture, and legal hold controls that gate planner and DNA asset workflows. Policies drive automated guardrail annotations across backend services and surface actionable telemetry for administrators via the new `/admin` experience.

## Key Components
- **Organizations** (`organizations` table, `/api/compliance/organizations`): capture residency defaults, encryption posture, and retention baselines per enterprise tenant.
- **Residency Policies** (`organization_residency_policies` table): define data-domain specific allowed regions, retention intervals, and guardrail flags. Policies extend organization defaults and drive enforcement in planner and DNA asset services.
- **Legal Holds** (`organization_legal_holds` table): record and track discovery or regulatory holds. Holds integrate with lifecycle timelines and can be released with audit notes.
- **Compliance Records** (`compliance_records` table): log guardrail evaluations, residency overrides, and encryption metadata for planner sessions, DNA assets, and other workflows. Records now include organization links, data domain tags, retention metadata, and guardrail flags.

## API Highlights
- `POST /api/compliance/organizations`: create an organization with residency defaults.
- `POST /api/compliance/organizations/{id}/policies`: upsert residency policies for a specific data domain.
- `POST /api/compliance/organizations/{id}/legal-holds`: activate a legal hold across planner or DNA resources.
- `POST /api/compliance/legal-holds/{hold_id}/release`: release an active legal hold with notes.
- `POST /api/compliance/records`: record guardrail-evaluated compliance checkpoints tied to residency policies.
- `GET /api/compliance/reports/export`: export a residency summary across organizations including policy counts, active holds, gaps, and record status totals.

## Service Integration
- **Planner (`services/cloning_planner.py`)** evaluates residency policies during session creation, annotates guardrail state, and records compliance entries. Violations propagate guardrail flags into planner timelines.
- **DNA Assets (`services/dna_assets.py`)** apply residency checks when creating or versioning assets. Violations produce guardrail events, compliance records, and metadata on the asset.
- **Compliance Service (`services/compliance.py`)** centralizes policy evaluation, legal hold lifecycle, record annotation, and report generation.

## Frontend Surfaces
- **Compliance Dashboard (`/compliance`)** lets operators log records, review guardrail flags, and inspect residency summaries.
- **Admin Hub (`/admin`)** offers organization onboarding, residency policy management, legal hold activation, and cross-tenant reporting.

## Operational Guidance
1. Configure organizations with the regions approved by legal/compliance.
2. Define residency policies for core data domains (planner telemetry, DNA assets, analytics exports).
3. Activate legal holds whenever discovery, audit, or regulatory workflows require data immutability.
4. Monitor the admin report to catch residency gaps or unexpected guardrail breaches.
5. Use compliance records surfaced on lifecycle timelines to trace how residency policies influenced planner and DNA asset decisions.
