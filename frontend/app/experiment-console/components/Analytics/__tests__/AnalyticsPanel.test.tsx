import { render, screen } from '@testing-library/react'
import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import GovernanceAnalyticsPanel from '../AnalyticsPanel'
import type { GovernanceAnalyticsReport } from '../../../../types'

const hooks = vi.hoisted(() => ({
  useGovernanceAnalytics: vi.fn(),
}))

vi.mock('../../../../hooks/useExperimentConsole', () => hooks)

const { useGovernanceAnalytics: mockUseGovernanceAnalytics } = hooks

describe('GovernanceAnalyticsPanel', () => {
  const report: GovernanceAnalyticsReport = {
    totals: {
      preview_count: 2,
      average_blocked_ratio: 0.25,
      total_new_blockers: 3,
      total_resolved_blockers: 4,
      average_sla_within_target_ratio: 0.75,
      total_baseline_versions: 5,
      total_rollbacks: 2,
      average_approval_latency_minutes: 180,
      average_publication_cadence_days: 4,
      reviewer_count: 1,
      streak_alert_count: 0,
    },
    results: [
      {
        execution_id: 'exec-1',
        preview_event_id: 'event-1',
        snapshot_id: 'snap-1',
        baseline_snapshot_id: null,
        generated_at: new Date('2024-01-01T00:00:00Z').toISOString(),
        stage_count: 4,
        blocked_stage_count: 1,
        blocked_ratio: 0.25,
        overrides_applied: 1,
        new_blocker_count: 2,
        resolved_blocker_count: 1,
        ladder_load: 5,
        sla_within_target_ratio: 0.5,
        mean_sla_delta_minutes: 10,
        sla_samples: [
          {
            stage_index: 0,
            predicted_due_at: new Date('2024-01-01T01:00:00Z').toISOString(),
            actual_completed_at: new Date('2024-01-01T00:45:00Z').toISOString(),
            delta_minutes: -15,
            within_target: true,
          },
        ],
        blocker_heatmap: [2],
        risk_level: 'medium',
        baseline_version_count: 3,
        approval_latency_minutes: 200,
        publication_cadence_days: 4,
        rollback_count: 1,
        blocker_churn_index: 1.5,
      },
      {
        execution_id: 'exec-2',
        preview_event_id: 'event-2',
        snapshot_id: 'snap-2',
        baseline_snapshot_id: null,
        generated_at: new Date('2024-01-02T00:00:00Z').toISOString(),
        stage_count: 3,
        blocked_stage_count: 0,
        blocked_ratio: 0,
        overrides_applied: 0,
        new_blocker_count: 1,
        resolved_blocker_count: 3,
        ladder_load: 3,
        sla_within_target_ratio: 1,
        mean_sla_delta_minutes: 0,
        sla_samples: [],
        blocker_heatmap: [],
        risk_level: 'low',
        baseline_version_count: 2,
        approval_latency_minutes: 160,
        publication_cadence_days: 3,
        rollback_count: 0,
        blocker_churn_index: 0.25,
      },
    ],
    reviewer_loads: [
      {
        reviewer_id: 'reviewer-1',
        reviewer_email: 'reviewer@example.com',
        reviewer_name: 'Reviewer Example',
        assigned_count: 5,
        completed_count: 5,
        pending_count: 0,
        average_latency_minutes: 140,
        latency_bands: [
          { label: 'under_2h', count: 1, start_minutes: null, end_minutes: 120 },
          { label: 'two_to_eight_h', count: 3, start_minutes: 120, end_minutes: 480 },
          { label: 'eight_to_day', count: 1, start_minutes: 480, end_minutes: 1440 },
          { label: 'over_day', count: 0, start_minutes: 1440, end_minutes: null },
        ],
        recent_blocked_ratio: 0.3,
        baseline_churn: 3.2,
        rollback_precursor_count: 1,
        current_publish_streak: 2,
        last_publish_at: '2024-01-02T00:00:00Z',
        streak_alert: false,
      },
    ],
  }

  beforeEach(() => {
    mockUseGovernanceAnalytics.mockReset()
  })

  it('renders loading state while query is in-flight', () => {
    mockUseGovernanceAnalytics.mockReturnValue({ isLoading: true })
    render(<GovernanceAnalyticsPanel executionId="exec-123" />)
    expect(screen.getByTestId('governance-analytics-loading')).toBeTruthy()
  })

  it('renders error state when query fails', () => {
    mockUseGovernanceAnalytics.mockReturnValue({ isLoading: false, isError: true })
    render(<GovernanceAnalyticsPanel executionId="exec-123" />)
    expect(screen.getByTestId('governance-analytics-error')).toBeTruthy()
  })

  it('displays analytics charts when data is available', () => {
    mockUseGovernanceAnalytics.mockReturnValue({
      isLoading: false,
      isError: false,
      data: report,
    })
    render(<GovernanceAnalyticsPanel executionId="exec-123" />)

    expect(screen.getByTestId('governance-analytics-panel')).toBeTruthy()
    expect(screen.getByTestId('sla-accuracy-chart')).toBeTruthy()
    expect(screen.getByTestId('blocker-heatmap')).toBeTruthy()
    expect(screen.getByTestId('ladder-load-chart')).toBeTruthy()
    expect(screen.getByTestId('baseline-lifecycle-card')).toBeTruthy()
    expect(screen.getByTestId('reviewer-load-heatmap')).toBeTruthy()
    expect(screen.getByTestId('reviewer-streak-alerts')).toBeTruthy()
    expect(screen.getByText(/Average SLA accuracy/i)).toBeTruthy()
    expect(screen.getByText(/Stage 2/)).toBeTruthy()
    expect(screen.getByText(/Average ladder load/i)).toBeTruthy()
    expect(screen.getByText(/Baseline Lifecycle Pulse/)).toBeTruthy()
    expect(screen.getByText(/Approval cadence/)).toBeTruthy()
  })
})
