import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach, type Mock } from 'vitest'

import type { LifecycleTimelineResponse } from '../../../types'
import { LifecycleSummaryPanel } from '../LifecycleSummaryPanel'

vi.mock('../../../hooks/useLifecycleNarrative', () => ({
  useLifecycleNarrative: vi.fn(),
}))

const { useLifecycleNarrative } = await import('../../../hooks/useLifecycleNarrative')
const mockUseLifecycleNarrative = useLifecycleNarrative as unknown as Mock

const responseFixture = (): LifecycleTimelineResponse => ({
  scope: { planner_session_id: 'planner-1' },
  summary: {
    total_events: 2,
    open_escalations: 1,
    active_guardrails: 1,
    latest_event_at: '2024-01-02T10:00:00.000Z',
    custody_state: 'under_review',
    context_chips: [
      { label: 'Planner', value: 'planner-1', kind: 'planner' },
      { label: 'Repository', value: 'vault', kind: 'repository' },
    ],
  },
  entries: [
    {
      entry_id: 'planner:stage-1',
      source: 'planner',
      event_type: 'planner.primers.completed',
      occurred_at: '2024-01-01T12:00:00.000Z',
      title: 'Primers · completed',
      summary: 'Primers verified',
      metadata: {
        checkpoint_key: 'primers',
        guardrail_flags: ['tm_range'],
      },
    },
    {
      entry_id: 'custody:log-1',
      source: 'custody',
      event_type: 'custody.transfer',
      occurred_at: '2024-01-02T08:00:00.000Z',
      title: 'Custody · transfer',
      summary: 'Moved to freezer',
      metadata: {
        guardrail_flags: [],
      },
    },
  ],
})

describe('LifecycleSummaryPanel', () => {
  beforeEach(() => {
    mockUseLifecycleNarrative.mockReset()
  })

  it('renders lifecycle summary and timeline entries', () => {
    mockUseLifecycleNarrative.mockReturnValue({
      data: responseFixture(),
      isLoading: false,
      isError: false,
    } as any)

    render(<LifecycleSummaryPanel scope={{ planner_session_id: 'planner-1' }} />)

    expect(screen.getByTestId('lifecycle-summary-panel')).toBeTruthy()
    expect(screen.getByText(/Lifecycle timeline/)).toBeTruthy()
    expect(screen.getByText(/2 events/)).toBeTruthy()
    expect(screen.getByText(/Primers · completed/)).toBeTruthy()
    expect(screen.getByText(/tm_range/)).toBeTruthy()
    expect(screen.getByText(/Guardrail activity detected/)).toBeTruthy()
  })

  it('renders loading state', () => {
    mockUseLifecycleNarrative.mockReturnValue({
      data: undefined,
      isLoading: true,
      isError: false,
    } as any)

    render(<LifecycleSummaryPanel scope={{ planner_session_id: 'planner-1' }} />)

    expect(screen.getByText(/Loading lifecycle timeline/)).toBeTruthy()
  })

  it('renders error state', () => {
    mockUseLifecycleNarrative.mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: true,
    } as any)

    render(<LifecycleSummaryPanel scope={{ planner_session_id: 'planner-1' }} />)

    expect(screen.getByText(/Unable to load lifecycle timeline/)).toBeTruthy()
  })
})

