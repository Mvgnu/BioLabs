import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { CloningPlannerEventPayload, CloningPlannerStageRecord } from '../../../types'
import { PlannerTimeline } from '../PlannerTimeline'

const eventFixture = (): CloningPlannerEventPayload => ({
  id: 'cursor-1',
  type: 'stage_completed',
  session_id: 'planner-1',
  status: 'ready_for_finalize',
  current_step: 'restriction',
  payload: { stage: 'primers' },
  guardrail_gate: { active: false, reasons: [] },
  guardrail_transition: { current: { active: false, reasons: [] }, previous: { active: false, reasons: [] } },
  branch: { active: 'branch-main' },
  checkpoint: { key: 'primers', payload: { status: 'primers_complete' } },
  timeline_cursor: 'cursor-1',
  timestamp: '2024-01-01T00:00:00.000Z',
})

const historyFixture = (): CloningPlannerStageRecord => ({
  id: 'record-1',
  stage: 'primers',
  attempt: 0,
  retry_count: 0,
  status: 'primers_complete',
  payload_metadata: {},
  guardrail_snapshot: {},
  metrics: {},
  review_state: {},
  checkpoint_key: 'primers',
  checkpoint_payload: { status: 'primers_complete' },
  guardrail_transition: { current: { active: false, reasons: [] }, previous: { active: false, reasons: [] } },
  timeline_position: 'cursor-1',
  branch_id: 'branch-main',
  created_at: '2024-01-01T00:00:00.000Z',
  updated_at: '2024-01-01T00:00:00.000Z',
  task_id: null,
  payload_path: null,
  started_at: null,
  completed_at: '2024-01-01T00:00:00.000Z',
  error: null,
})

describe('PlannerTimeline', () => {
  it('renders timeline entries and allows scrubbing', () => {
    render(
      <PlannerTimeline
        events={[eventFixture()]}
        stageHistory={[historyFixture()]}
        activeBranchId="branch-main"
      />,
    )

    expect(screen.getByTestId('planner-timeline')).toBeTruthy()
    expect(screen.getByText(/Timeline replay/)).toBeTruthy()
    expect(screen.getByText(/Scrub to event/)).toBeTruthy()

    const slider = screen.getByTestId('planner-timeline-slider') as HTMLInputElement
    expect(slider.value).toBe('0')
    fireEvent.change(slider, { target: { value: '0' } })
    expect(slider.value).toBe('0')
  })
})

