import React from 'react'
import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { GuardrailBadge } from '../GuardrailBadge'
import { GuardrailEscalationPrompt } from '../GuardrailEscalationPrompt'
import { GuardrailQCDecisionLoop } from '../GuardrailQCDecisionLoop'
import { GuardrailReviewerHandoff } from '../GuardrailReviewerHandoff'

// purpose: verify guardrail primitives render expected state and invoke callbacks
// status: experimental

describe('Guardrail components', () => {
  it('renders guardrail badge with metadata tags', () => {
    render(
      <GuardrailBadge label="Primers" state="review" metadataTags={['high_tm', 'gc_warning']} detail="Tm span 12°C" />,
    )

    expect(screen.getByText('Primers')).toBeTruthy()
    expect(screen.getByText('Review')).toBeTruthy()
    expect(screen.getByText('high_tm')).toBeTruthy()
    expect(screen.getByText('Tm span 12°C')).toBeTruthy()
  })

  it('emits acknowledgement for escalation prompt', () => {
    const ack = vi.fn()
    render(
      <GuardrailEscalationPrompt
        severity="critical"
        title="QC Blocked"
        message="Signal to noise below threshold"
        metadata={{ snr: 9.4, breach: true }}
        onAcknowledge={ack}
        actionLabel="Escalate"
      />,
    )

    fireEvent.click(screen.getByText('Escalate'))
    expect(ack).toHaveBeenCalledTimes(1)
    expect(screen.getByText('snr')).toBeTruthy()
  })

  it('shows reviewer handoff information and notify callback', () => {
    const notify = vi.fn()
    render(
      <GuardrailReviewerHandoff
        reviewerName="Avery Ops"
        reviewerEmail="avery@example.com"
        reviewerRole="Governance Lead"
        notes="Awaiting updated chromatogram"
        pendingSince="2024-01-01T00:00:00.000Z"
        onNotify={notify}
      />,
    )

    expect(screen.getByText('Avery Ops')).toBeTruthy()
    fireEvent.click(screen.getByText('Notify reviewer'))
    expect(notify).toHaveBeenCalledTimes(1)
    expect(screen.getByTestId('guardrail-reviewer-handoff')).toBeTruthy()
  })

  it('renders QC decision loop and triggers acknowledgement', () => {
    const ack = vi.fn()
    render(
      <GuardrailQCDecisionLoop
        artifacts={[
          {
            id: 'artifact-1',
            artifact_name: 'Sample A',
            sample_id: 'sample-a',
            metrics: { signal_to_noise: 9.4, dropoff: 2.1 },
            thresholds: { signal_to_noise: 15 },
            reviewer_decision: null,
            reviewer_notes: null,
            reviewer_id: null,
            stage_record_id: 'record-1',
            reviewer_email: undefined,
            storage_path: null,
            trace_path: null,
            metrics_summary: undefined,
            reviewer_name: undefined,
            thresholds_summary: undefined,
            reviewer_decision_at: undefined,
            created_at: null,
            updated_at: null,
          } as any,
        ]}
        onAcknowledge={ack}
      />,
    )

    expect(screen.getByText('Sample A')).toBeTruthy()
    fireEvent.click(screen.getByText('Acknowledge review'))
    expect(ack).toHaveBeenCalledTimes(1)
  })
})

