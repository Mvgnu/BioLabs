# Community Discovery Page

- purpose: render the discovery hub for federated community portfolios.
- status: experimental
- depends_on: ../hooks/useCommunity.ts, ../../docs/community/README.md

## components
- **Portfolio filters**: search, license, guardrail toggles, and portfolio creation form.
- **Insight panels**: personalized review queue, trending releases, and replay checkpoint inspector.
- **Portfolio cards**: guardrail badges, asset panels with inline diff preview, and engagement actions.

## interactions
- Uses React Query hooks in `../hooks/useCommunity.ts` to fetch portfolios, feeds, and trending analytics.
- Engagement buttons invoke `useRecordPortfolioEngagement` to emit view/bookmark/star/review signals.
- Portfolio creation uses `useCreatePortfolio`; guardrail state automatically adjusts via backend service responses.

## testing
- Covered by `frontend/app/community/__tests__/CommunityPage.test.tsx` using Vitest + React Testing Library.
