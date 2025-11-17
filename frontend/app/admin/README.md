# Admin Compliance Hub

- purpose: render enterprise compliance controls for organizations, residency policies, and legal holds
- status: active
- depends_on: `frontend/app/hooks/useCompliance.ts`, `/api/compliance/*` endpoints, React Query store configuration
- key_routes: `/admin`
- inputs: React Query data for organizations, policies, legal holds, compliance report; user form submissions for creating orgs, policies, and legal holds
- outputs: mutation calls that create/update compliance entities and display guardrail summaries for administrators

This page layers administrative tooling on top of the compliance API. It lets operators:

1. Register organizations with residency defaults and encryption posture.
2. Upsert domain-specific residency policies with retention and guardrail metadata.
3. Activate or release legal holds across shared resources.
4. Review generated residency and guardrail summaries per organization.

React Query hooks handle cache invalidation across the admin and operations surfaces to keep dashboards in sync after each mutation.
