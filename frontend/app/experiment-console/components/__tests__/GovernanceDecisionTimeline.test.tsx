import { fireEvent, render, screen } from '@testing-library/react'
import React from 'react'
import { describe, expect, it, vi } from 'vitest'

import GovernanceDecisionTimeline from '../Timeline/Governance/DecisionTimeline'

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
}

describe('GovernanceDecisionTimeline', () => {
  it('renders governance entries with summary and metadata', () => {
    render(<GovernanceDecisionTimeline entries={[baseEntry]} />)

    expect(screen.getByText('Governance Decisions')).toBeTruthy()
    expect(screen.getByText('Override Recommendation')).toBeTruthy()
    expect(screen.getByText('Reassign reviewer to balance load')).toBeTruthy()
    expect(screen.getByText(/cadence_overload/i)).toBeTruthy()
    expect(screen.getByText(/Pat Researcher/)).toBeTruthy()
  })

  it('invokes load more callback when button pressed', () => {
    const handleLoadMore = vi.fn()
    render(
      <GovernanceDecisionTimeline
        entries={[baseEntry]}
        hasMore
        onLoadMore={handleLoadMore}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /load more/i }))
    expect(handleLoadMore).toHaveBeenCalledTimes(1)
  })

  it('shows loading state when awaiting entries', () => {
    render(<GovernanceDecisionTimeline entries={[]} isLoading />)

    expect(screen.getByText(/Loading governance activity/)).toBeTruthy()
  })
})
