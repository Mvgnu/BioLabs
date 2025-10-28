import { render, screen } from '@testing-library/react'
import React from 'react'
import { describe, expect, it } from 'vitest'
import GuardrailHealthDashboard from '../GuardrailHealthDashboard'
import type {
  GovernanceGuardrailHealthReport,
  GovernanceGuardrailQueueEntry,
} from '../../../types'

const buildEntry = (overrides: Partial<GovernanceGuardrailQueueEntry> = {}): GovernanceGuardrailQueueEntry => ({
  export_id: 'export-1',
  execution_id: 'execution-1',
  version: 1,
  state: 'awaiting_approval',
  event: 'narrative_export.packaging.awaiting_approval',
  approval_status: 'pending',
  artifact_status: 'queued',
  packaging_attempts: 0,
  guardrail_state: null,
  projected_delay_minutes: null,
  pending_stage_id: 'stage-1',
  pending_stage_index: 0,
  pending_stage_status: 'in_progress',
  pending_stage_due_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  context: { pending_stage_status: 'in_progress' },
  ...overrides,
})

const buildReport = (
  overrides: Partial<GovernanceGuardrailHealthReport> = {},
): GovernanceGuardrailHealthReport => ({
  totals: {
    total_exports: 1,
    blocked: 0,
    awaiting_approval: 1,
    queued: 0,
    ready: 0,
    failed: 0,
    ...(overrides.totals ?? {}),
  },
  state_breakdown: overrides.state_breakdown ?? { awaiting_approval: 1 },
  queue: overrides.queue ?? [buildEntry()],
})

describe('GuardrailHealthDashboard', () => {
  it('renders loading state', () => {
    render(<GuardrailHealthDashboard report={undefined} isLoading error={null} />)
    expect(screen.getByRole('heading', { name: /loading guardrail health/i })).toBeTruthy()
  })

  it('renders empty state when no telemetry', () => {
    render(
      <GuardrailHealthDashboard
        report={buildReport({ totals: { total_exports: 0, blocked: 0, awaiting_approval: 0, queued: 0, ready: 0, failed: 0 } })}
        isLoading={false}
        error={null}
      />,
    )
    expect(screen.getByText(/no guardrail activity yet/i)).toBeTruthy()
  })

  it('renders metrics and queue entries', () => {
    const report = buildReport()
    render(<GuardrailHealthDashboard report={report} isLoading={false} error={null} />)
    expect(screen.getByText(/exports tracked/i)).toBeTruthy()
    expect(screen.getByText(/state breakdown/i)).toBeTruthy()
    expect(screen.getByRole('heading', { name: /guardrail queue/i })).toBeTruthy()
    expect(screen.getByText('export-1')).toBeTruthy()
  })
})
