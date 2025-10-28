import { fireEvent, render, screen } from '@testing-library/react'
import React from 'react'
import { describe, expect, it, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

import GovernanceDecisionTimeline from '../Timeline/Governance/DecisionTimeline'

const createWrapper = () => {
  const client = new QueryClient()
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
}

const baseEntry = {
  entry_id: 'event-1',
  entry_type: 'override_recommendation' as const,
  occurred_at: new Date('2024-04-01T15:00:00Z').toISOString(),
  execution_id: 'exec-1',
  baseline_id: null,
  rule_key: 'cadence_overload',
  action: 'reassign',
  status: 'accepted',
  summary: 'Reassign reviewer to balance load',
  detail: { priority: 'high', reviewer_id: 'rev-1' },
  actor: { id: 'user-1', name: 'Pat Researcher', email: 'pat@example.com' },
  lineage: {
    scenario: { id: 'scenario-1', name: 'Scenario Alpha' },
    notebook_entry: { id: 'notebook-1', title: 'Review Notebook' },
    captured_at: new Date('2024-04-01T14:00:00Z').toISOString(),
    captured_by: { id: 'user-2', name: 'Coordinator Cole', email: 'cole@example.com' },
    metadata: { source: 'unit-test' },
  },
}

describe('GovernanceDecisionTimeline', () => {
  it('renders governance entries with summary and metadata', () => {
    render(<GovernanceDecisionTimeline entries={[baseEntry]} />, {
      wrapper: createWrapper(),
    })

    expect(screen.getByText('Governance Decisions')).toBeTruthy()
    expect(screen.getByText('Override Recommendation')).toBeTruthy()
    expect(screen.getByText('Reassign reviewer to balance load')).toBeTruthy()
    expect(screen.getByText(/cadence_overload/i)).toBeTruthy()
    expect(screen.getByText(/Pat Researcher/)).toBeTruthy()
    expect(screen.getByText('Lineage Context')).toBeTruthy()
    expect(screen.getByText('Scenario Alpha')).toBeTruthy()
  })

  it('invokes load more callback when button pressed', () => {
    const handleLoadMore = vi.fn()
    render(
      <GovernanceDecisionTimeline
        entries={[baseEntry]}
        hasMore
        onLoadMore={handleLoadMore}
      />,
      { wrapper: createWrapper() },
    )

    fireEvent.click(screen.getByRole('button', { name: /load more/i }))
    expect(handleLoadMore).toHaveBeenCalledTimes(1)
  })

  it('shows loading state when awaiting entries', () => {
    render(<GovernanceDecisionTimeline entries={[]} isLoading />, {
      wrapper: createWrapper(),
    })

    expect(screen.getByText(/Loading governance activity/)).toBeTruthy()
  })

  it('renders lineage analytics widget for analytics snapshots', () => {
    const analyticsEntry = {
      ...baseEntry,
      entry_id: 'analytics-1',
      entry_type: 'analytics_snapshot' as const,
      summary: 'Reviewer cadence snapshot',
      detail: {
        lineage_summary: {
          scenarios: [
            {
              scenario_id: 'scenario-analytics',
              scenario_name: 'Scenario Analytics',
              folder_name: null,
              executed_count: 4,
              reversed_count: 1,
              net_count: 3,
            },
          ],
          notebooks: [],
        },
      },
    }

    render(<GovernanceDecisionTimeline entries={[analyticsEntry]} />, {
      wrapper: createWrapper(),
    })

    expect(screen.getByText('Lineage override analytics')).toBeTruthy()
    expect(screen.getByText('Scenario Analytics')).toBeTruthy()
  })
})
