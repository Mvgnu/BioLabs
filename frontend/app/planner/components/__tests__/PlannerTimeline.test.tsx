import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

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
  resume_token: {
    session_id: 'planner-1',
    checkpoint: 'primers',
    branch_id: 'branch-main',
    timeline_cursor: 'cursor-1',
  },
  branch_lineage_delta: {
    branch_id: 'branch-main',
    branch_label: 'Main',
    history_length: 3,
  },
  mitigation_hints: [{ category: 'custody', action: 'resolve_escalations', pending: 1 }],
  branch_comparison: {
    reference_branch_id: 'branch-alt',
    history_delta: 2,
    ahead_checkpoints: [
      {
        index: 2,
        stage: 'assembly',
        checkpoint_key: 'assembly',
        status: 'completed',
        timeline_position: 'cursor-2',
        guardrail_state: 'ok',
        guardrail_active: false,
        resume_ready: true,
        custody_summary: {
          max_severity: 'critical',
          open_drill_count: 1,
          open_escalations: 0,
          pending_event_count: 0,
          resume_ready: true,
        },
      },
    ],
    missing_checkpoints: [
      {
        index: 1,
        stage: 'qc',
        checkpoint_key: 'qc',
        status: 'pending',
        timeline_position: 'cursor-ref-2',
        guardrail_state: 'halted',
        guardrail_active: true,
        resume_ready: false,
        custody_summary: {
          max_severity: 'warning',
          open_drill_count: 0,
          open_escalations: 1,
          pending_event_count: 0,
          resume_ready: false,
        },
      },
    ],
    divergent_stages: [
      {
        index: 1,
        primary: {
          index: 1,
          stage: 'primers',
          checkpoint_key: 'primers',
          status: 'completed',
          timeline_position: 'cursor-1',
          guardrail_state: 'ok',
          guardrail_active: false,
          resume_ready: true,
          custody_summary: {
            max_severity: 'critical',
            open_drill_count: 1,
            open_escalations: 0,
            pending_event_count: 1,
            resume_ready: true,
          },
        },
        reference: {
          index: 1,
          stage: 'primers',
          checkpoint_key: 'primers',
          status: 'blocked',
          timeline_position: 'cursor-ref-1',
          guardrail_state: 'halted',
          guardrail_active: true,
          resume_ready: false,
          custody_summary: {
            max_severity: 'warning',
            open_drill_count: 0,
            open_escalations: 1,
            pending_event_count: 0,
            resume_ready: false,
          },
        },
      },
    ],
    primary_custody_metrics: {
      checkpoint_count: 3,
      open_drill_total: 2,
      open_escalation_total: 1,
      pending_event_total: 1,
      resume_ready_count: 2,
      blocked_checkpoint_count: 1,
      max_severity: 'critical',
    },
    reference_custody_metrics: {
      checkpoint_count: 2,
      open_drill_total: 0,
      open_escalation_total: 1,
      pending_event_total: 0,
      resume_ready_count: 1,
      blocked_checkpoint_count: 1,
      max_severity: 'warning',
    },
    custody_deltas: {
      severity_delta: 2,
      open_drill_delta: 2,
      open_escalation_delta: 0,
      pending_event_delta: 1,
      blocked_checkpoint_delta: 0,
      resume_ready_delta: 1,
    },
  },
  recovery_bundle: {
    stage: 'primers',
    recommended_stage: 'primers',
    resume_token: {
      session_id: 'planner-1',
      checkpoint: 'primers',
      branch_id: 'branch-main',
      timeline_cursor: 'cursor-1',
    },
    branch_lineage: {
      branch_id: 'branch-main',
      branch_label: 'Main',
      history_length: 3,
    },
    mitigation_hints: [{ category: 'custody', action: 'resolve_escalations', pending: 1 }],
    guardrail_reasons: ['custody_status:halted'],
    open_escalations: 1,
    pending_events: [{ event_id: 'evt-1', open_escalations: ['esc-1'] }],
    holds: [{ stage: 'primers', status: 'primers_guardrail_hold' }],
    drill_summaries: [
      {
        event_id: 'evt-1',
        status: 'open',
        max_severity: 'critical',
        open_escalations: ['esc-1'],
        resume_ready: false,
      },
    ],
    resume_ready: true,
  },
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
  resume_token: {
    session_id: 'planner-1',
    checkpoint: 'primers',
    branch_id: 'branch-main',
    timeline_cursor: 'cursor-1',
  },
    branch_lineage: {
      branch_id: 'branch-main',
      branch_label: 'Main',
      history_length: 3,
    },
    mitigation_hints: [{ category: 'custody', action: 'resolve_escalations', pending: 1 }],
    recovery_bundle: {
      stage: 'primers',
      resume_token: {
        session_id: 'planner-1',
        checkpoint: 'primers',
        branch_id: 'branch-main',
        timeline_cursor: 'cursor-1',
      },
      branch_lineage: {
        branch_id: 'branch-main',
        branch_label: 'Main',
        history_length: 3,
      },
      mitigation_hints: [{ category: 'custody', action: 'resolve_escalations', pending: 1 }],
      guardrail_reasons: ['custody_status:halted'],
      open_escalations: 1,
      open_drill_count: 1,
      pending_events: [{ event_id: 'evt-1', max_severity: 'critical' }],
      drill_summaries: [
        {
          event_id: 'evt-1',
          status: 'open',
          max_severity: 'critical',
          open_escalations: ['esc-1'],
          resume_ready: false,
        },
      ],
      resume_ready: true,
    },
  custody_summary: {
    max_severity: 'critical',
    open_drill_count: 1,
    open_escalations: 1,
    pending_event_count: 1,
    resume_ready: true,
  },
})

describe('PlannerTimeline', () => {
  it('renders timeline entries and allows scrubbing', () => {
    const onResume = vi.fn()
    render(
      <PlannerTimeline
        events={[eventFixture()]}
        stageHistory={[historyFixture()]}
        activeBranchId="branch-main"
        replayWindow={[historyFixture()]}
        comparisonWindow={[historyFixture()]}
        mitigationHints={[{ category: 'custody', action: 'resolve_escalations', pending: 1 }]}
        recoveryBundle={{
          stage: 'restriction',
          recommended_stage: 'restriction',
          resume_token: {
            session_id: 'planner-1',
            checkpoint: 'restriction',
            branch_id: 'branch-main',
            timeline_cursor: 'cursor-2',
          },
          guardrail_reasons: ['custody_status:halted'],
          open_escalations: 1,
          pending_events: [{ event_id: 'evt-2', open_escalations: ['esc-2'] }],
          holds: [{ stage: 'primers', status: 'primers_guardrail_hold' }],
          drill_summaries: [
            {
              event_id: 'evt-3',
              status: 'open',
              max_severity: 'critical',
              open_escalations: ['esc-5'],
              resume_ready: false,
            },
            {
              event_id: 'evt-4',
              status: 'resolved',
              max_severity: 'warning',
              open_escalations: [],
              resume_ready: true,
            },
          ],
          resume_ready: true,
        }}
        onResume={onResume}
        resumePending={false}
      />,
    )

    expect(screen.getByTestId('planner-timeline')).toBeTruthy()
    expect(screen.getByText(/Timeline replay/)).toBeTruthy()
    expect(screen.getByText(/Scrub to event/)).toBeTruthy()
    expect(screen.getByText(/Replay checkpoints: 1/)).toBeTruthy()
    expect(screen.getByText(/Comparison backlog: 1/)).toBeTruthy()
    expect(screen.getByTestId('planner-timeline-recovery-bundle')).toBeTruthy()
    expect(screen.getByText(/Checkpoint recovery/)).toBeTruthy()
    expect(screen.getByText(/Lineage: Main/)).toBeTruthy()
    expect(screen.getByText('+2 vs branch branch-a')).toBeTruthy()
    expect(screen.getByText(/Ahead of reference: assembly/)).toBeTruthy()
    expect(screen.getByText(/Missing from branch: qc/)).toBeTruthy()
    expect(screen.getByText(/Divergent at primers/)).toBeTruthy()
    expect(screen.getByText(/Custody severity at primers/)).toBeTruthy()
    expect(screen.getByText(/Branch severity: CRITICAL vs WARNING/)).toBeTruthy()
    expect(screen.getByText(/Open drill delta: \+2/)).toBeTruthy()
    expect(screen.getByText(/Pending drill delta: \+1/)).toBeTruthy()
    expect(screen.getByTestId('planner-timeline-mitigations')).toBeTruthy()
    expect(screen.getByText(/Pending drills: 1/)).toBeTruthy()
    const overlaySummaries = screen.getAllByText((content) => content.startsWith('Drill overlays:'))
    expect(overlaySummaries.length).toBeGreaterThan(0)
    expect(overlaySummaries[0].textContent).toContain('open')
    expect(screen.getByText(/Custody drills: 1/)).toBeTruthy()
    expect(screen.getByText(/Custody severity: CRITICAL/)).toBeTruthy()
    expect(
      screen.getByText(
        /evt-3 \(open\) · severity: critical · open escalations: 1 – resume blocked/,
      ),
    ).toBeTruthy()

    const resumeButton = screen.getByText(/Resume from checkpoint/)
    fireEvent.click(resumeButton)
    expect(onResume).toHaveBeenCalledTimes(1)

    const slider = screen.getByTestId('planner-timeline-slider') as HTMLInputElement
    expect(slider.value).toBe('0')
    fireEvent.change(slider, { target: { value: '0' } })
    expect(slider.value).toBe('0')
  })
})

