import { fireEvent, render, screen } from '@testing-library/react'
import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import BaselinesPanel from '../Baselines/BaselinesPanel'

const hooks = vi.hoisted(() => ({
  useGovernanceBaselines: vi.fn(),
  useSubmitBaseline: vi.fn(),
  useReviewBaseline: vi.fn(),
  usePublishBaseline: vi.fn(),
  useRollbackBaseline: vi.fn(),
}))

vi.mock('../../../hooks/useExperimentConsole', () => hooks)

const {
  useGovernanceBaselines: mockUseGovernanceBaselines,
  useSubmitBaseline: mockUseSubmitBaseline,
  useReviewBaseline: mockUseReviewBaseline,
  usePublishBaseline: mockUsePublishBaseline,
  useRollbackBaseline: mockUseRollbackBaseline,
} = hooks

describe('BaselinesPanel', () => {
  const baseline = {
    id: 'baseline-1',
    execution_id: 'exec-1',
    template_id: 'tpl-1',
    team_id: null,
    name: 'QA Ladder',
    description: 'Expanded SLA window',
    status: 'submitted',
    labels: [
      { key: 'environment', value: 'production' },
      { key: 'ladder', value: 'qa' },
    ],
    reviewer_ids: ['reviewer-1'],
    version_number: null,
    is_current: false,
    submitted_by_id: 'scientist-1',
    submitted_at: new Date('2024-03-01T10:00:00Z').toISOString(),
    reviewed_by_id: null,
    reviewed_at: null,
    review_notes: null,
    published_by_id: null,
    published_at: null,
    publish_notes: null,
    rollback_of_id: null,
    rolled_back_by_id: null,
    rolled_back_at: null,
    rollback_notes: null,
    created_at: new Date('2024-03-01T10:00:00Z').toISOString(),
    updated_at: new Date('2024-03-01T10:00:00Z').toISOString(),
    events: [
      {
        id: 'event-1',
        baseline_id: 'baseline-1',
        action: 'submitted',
        notes: 'Created by scientist-1',
        detail: { reviewer_count: 1 },
        performed_by_id: 'scientist-1',
        created_at: new Date('2024-03-01T10:00:00Z').toISOString(),
      },
    ],
  }

  beforeEach(() => {
    mockUseGovernanceBaselines.mockReturnValue({
      data: [baseline],
      isLoading: false,
      isError: false,
    })
    mockUseSubmitBaseline.mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
      isError: false,
      error: null,
    })
    mockUseReviewBaseline.mockReturnValue({ mutate: vi.fn() })
    mockUsePublishBaseline.mockReturnValue({ mutate: vi.fn() })
    mockUseRollbackBaseline.mockReturnValue({ mutate: vi.fn() })
    vi.spyOn(window, 'prompt').mockReturnValue('Looks good')
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders baseline queue and timeline with actions', () => {
    render(
      <BaselinesPanel
        executionId="exec-1"
        templateId="tpl-1"
        templateName="QA Ladder"
        canManage
        currentUserId="reviewer-1"
      />,
    )

    expect(screen.getByText('Baseline governance')).toBeTruthy()
    expect(screen.getAllByText('QA Ladder').length).toBeGreaterThan(0)
    expect(screen.getByText(/Submitted/)).toBeTruthy()
    expect(screen.getByText(/Lifecycle History/i)).toBeTruthy()

    const approveButton = screen.getByRole('button', { name: /approve/i })
    fireEvent.click(approveButton)

    const reviewMutation = mockUseReviewBaseline.mock.results[0].value
    expect(reviewMutation.mutate).toHaveBeenCalledWith({
      baselineId: 'baseline-1',
      payload: { decision: 'approve', notes: 'Looks good' },
    })
  })

  it('disables submission form when user cannot manage baselines', () => {
    mockUseGovernanceBaselines.mockReturnValue({ data: [], isLoading: false, isError: false })
    render(
      <BaselinesPanel
        executionId="exec-1"
        templateId="tpl-1"
        templateName="QA Ladder"
        canManage={false}
      />,
    )

    expect(screen.getByText(/view-only access/i)).toBeTruthy()
    const nameInputs = screen.getAllByLabelText(/baseline name/i) as HTMLInputElement[]
    expect(nameInputs.some((input) => input.disabled)).toBe(true)
  })
})
