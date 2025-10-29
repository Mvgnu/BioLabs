import { fireEvent, render, screen } from '@testing-library/react'
import React from 'react'
import { describe, expect, it, vi } from 'vitest'
import CustodyEscalationPanel from '../CustodyEscalationPanel'
import type { CustodyEscalation, FreezerFaultRecord } from '../../../types'

const buildEscalation = (overrides: Partial<CustodyEscalation> = {}): CustodyEscalation => ({
  id: 'esc-1',
  status: 'open',
  severity: 'critical',
  reason: 'capacity exceeded in Rack A',
  due_at: new Date().toISOString(),
  acknowledged_at: null,
  resolved_at: null,
  assigned_to_id: null,
  guardrail_flags: ['capacity.exceeded'],
  notifications: [],
  meta: {},
  log_id: null,
  freezer_unit_id: null,
  compartment_id: 'comp-1',
  asset_version_id: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  ...overrides,
})

const buildFault = (overrides: Partial<FreezerFaultRecord> = {}): FreezerFaultRecord => ({
  id: 'fault-1',
  freezer_unit_id: 'freezer-1',
  compartment_id: 'comp-1',
  fault_type: 'temperature.high',
  severity: 'critical',
  guardrail_flag: 'fault.temperature.high',
  occurred_at: new Date().toISOString(),
  resolved_at: null,
  meta: {},
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  ...overrides,
})

describe('CustodyEscalationPanel', () => {
  it('renders empty states when no escalations or faults', () => {
    render(
      <CustodyEscalationPanel
        escalations={[]}
        faults={[]}
        isEscalationLoading={false}
        isFaultLoading={false}
        onAcknowledge={() => {}}
        onResolve={() => {}}
        onNotify={() => {}}
      />,
    )

    expect(screen.getByText(/no active custody escalations/i)).toBeTruthy()
    expect(screen.getByText(/no freezer faults detected/i)).toBeTruthy()
  })

  it('renders escalations and faults with action callbacks', () => {
    const acknowledge = vi.fn()
    const resolve = vi.fn()
    const notify = vi.fn()

    render(
      <CustodyEscalationPanel
        escalations={[buildEscalation()]}
        faults={[buildFault()]}
        isEscalationLoading={false}
        isFaultLoading={false}
        onAcknowledge={acknowledge}
        onResolve={resolve}
        onNotify={notify}
      />,
    )

    const acknowledgeButton = screen.getByRole('button', { name: /acknowledge/i })
    fireEvent.click(acknowledgeButton)
    expect(acknowledge).toHaveBeenCalledWith('esc-1')

    const notifyButton = screen.getByRole('button', { name: /notify team/i })
    fireEvent.click(notifyButton)
    expect(notify).toHaveBeenCalledWith('esc-1')

    const resolveButton = screen.getByRole('button', { name: /resolve/i })
    fireEvent.click(resolveButton)
    expect(resolve).toHaveBeenCalledWith('esc-1')

    expect(screen.getAllByText(/temperature\.high/i).length).toBeGreaterThan(0)
  })
})
