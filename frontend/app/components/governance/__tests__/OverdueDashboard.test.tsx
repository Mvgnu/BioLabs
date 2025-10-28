import { render, screen } from '@testing-library/react'
import React from 'react'
import { describe, expect, it } from 'vitest'
import OverdueDashboard from '../OverdueDashboard'
import type {
  GovernanceOverdueStageSummary,
  GovernanceStageMetrics,
} from '../../../types'

describe('OverdueDashboard', () => {
  const buildSummary = (overrides: Partial<GovernanceOverdueStageSummary> = {}): GovernanceOverdueStageSummary => ({
    total_overdue: 3,
    open_overdue: 2,
    resolved_overdue: 1,
    overdue_exports: ['exp-1'],
    role_counts: { scientist: 2, qa: 1 },
    mean_open_minutes: 125,
    open_age_buckets: { lt60: 1, '60to180': 1, gt180: 1 },
    trend: [],
    stage_samples: [
      {
        stage_id: 'stage-1',
        export_id: 'exp-1',
        sequence_index: 0,
        status: 'in_progress',
        role: 'scientist',
        due_at: new Date().toISOString(),
        detected_at: new Date().toISOString(),
      },
    ],
    ...overrides,
  })

  it('renders loading state', () => {
    render(
      <OverdueDashboard
        isLoading
        summary={undefined}
        stageMetrics={undefined}
        error={null}
      />,
    )
    expect(
      screen.getByRole('heading', { name: /loading overdue governance analytics/i }),
    ).toBeTruthy()
  })

  it('renders empty state when no overdue data', () => {
    render(
      <OverdueDashboard
        isLoading={false}
        summary={buildSummary({ total_overdue: 0 })}
        stageMetrics={undefined}
        error={null}
      />,
    )
    expect(screen.getByText(/no overdue ladders detected/i)).toBeTruthy()
  })

  it('renders metrics and escalation links', () => {
    const summary = buildSummary()
    const metrics: Record<string, GovernanceStageMetrics> = {
      'exp-1': {
        total: 2,
        overdue_count: 1,
        mean_resolution_minutes: 42,
        status_counts: { completed: 1 },
        stage_details: {
          '1': {
            status: 'completed',
            breached: true,
            resolution_minutes: 42,
            due_at: new Date().toISOString(),
            completed_at: new Date().toISOString(),
          },
        },
      },
    }

    render(
      <OverdueDashboard
        isLoading={false}
        summary={summary}
        stageMetrics={metrics}
        error={null}
      />,
    )

    expect(screen.getByRole('heading', { name: /role pressure map/i })).toBeTruthy()
    expect(screen.getByRole('heading', { name: /overdue stage queue/i })).toBeTruthy()
    const escalateLink = screen.getByRole('link', { name: /escalate/i })
    expect(escalateLink.getAttribute('href')).toContain('mailto:governance-ops@biolabs.local')
  })
})
