# Community Discovery Network

## purpose
- Document the guardrail-aware community portfolio system linking DNA assets, protocol templates, and planner sessions.
- Explain discovery APIs, personalized feeds, and moderation workflows for inter-org collaboration.

## overview
The community discovery surface exposes **community portfolios** that federate DNA knowledge, planner checkpoints, and licensing metadata. Each portfolio aggregates:

- Linked assets (DNA, protocols, planner sessions) with deterministic guardrail snapshots.
- Provenance and mitigation histories collected from guardrail events and planner guardrail state.
- Replay checkpoints that enable planners to resume validated runs.
- Engagement scoring sourced from bookmarks, stars, and review interactions.

## api summary
- `GET /api/community/portfolios` – list public or restricted portfolios with guardrail context.
- `POST /api/community/portfolios` – create a portfolio with optional assets; guardrail lineage is derived automatically.
- `POST /api/community/portfolios/{id}/assets` – attach additional assets and refresh provenance.
- `POST /api/community/portfolios/{id}/engagements` – record bookmark/star/view/review signals that update discovery ranking.
- `POST /api/community/portfolios/{id}/moderation` – resolve guardrail escalations and transition portfolio status.
- `GET /api/community/feed` – personalized feed reflecting recent engagements and guardrail readiness.
- `GET /api/community/trending` – trending summary across 24h/7d/30d windows based on engagement deltas.

## frontend experience
The Next.js discovery hub (`frontend/app/community/page.tsx`) provides:

- Filterable portfolio catalog with license and guardrail badges.
- Personalized review queue and trending guardrail-ready releases.
- Replay checkpoint inspector for planner teams.
- Inline diff previews using asset metadata and engagement controls to emit review events.

## moderation & guardrails
Moderation integrates custody guardrail outcomes:

- Guardrail events on DNA assets seed mitigation history and trigger review status.
- Portfolio moderation clears or blocks publication while recording `CommunityModerationEvent` timelines.
- Engagement analytics exclude blocked portfolios from discovery feeds.

## testing
Automated coverage validates:

- Portfolio creation and lineage compilation (`backend/app/tests/test_community.py`).
- Analytics integration for trending portfolios (`backend/app/tests/test_analytics.py`).
- Discovery UI behaviour (`frontend/app/community/__tests__/CommunityPage.test.tsx`).

## status
- status: experimental
- related_docs: docs/sharing/README.md, docs/instrumentation/README.md
