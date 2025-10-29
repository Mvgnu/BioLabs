import { fireEvent, render, screen } from '@testing-library/react'
import React from 'react'
import { describe, expect, it, vi } from 'vitest'
import CustodyEscalationPanel from '../CustodyEscalationPanel'
import type {
  CustodyEscalation,
  CustodyProtocolExecution,
  FreezerFaultRecord,
} from '../../../types'

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
  protocol_execution_id: 'exec-1',
  execution_event_id: 'event-1',
  protocol_execution: {
    id: 'exec-1',
    status: 'running',
    run_by: 'user-1',
    template_id: 'tpl-1',
    template_name: 'QC workflow',
    guardrail_status: 'halted',
    guardrail_state: { last_synced_at: new Date().toISOString() },
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  },
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

const buildProtocolSnapshot = (
  overrides: Partial<CustodyProtocolExecution> = {},
): CustodyProtocolExecution => ({
  id: 'exec-1',
  status: 'running',
  guardrail_status: 'halted',
  guardrail_state: { last_synced_at: new Date().toISOString() },
  template_id: 'tpl-1',
  template_name: 'QC workflow',
  run_by: 'user-1',
  open_escalations: 1,
  open_drill_count: 1,
  qc_backpressure: true,
  event_overlays: {
    'event-1': {
      mitigation_checklist: ['Relocate or thaw samples to restore compartment capacity.'],
      open_escalation_ids: ['esc-1'],
      open_drill_count: 1,
      max_severity: 'critical',
    },
  },
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
        protocols={[]}
        isProtocolLoading={false}
        protocolError={null}
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
        protocols={[buildProtocolSnapshot()]}
        isProtocolLoading={false}
        protocolError={null}
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
    expect(screen.getByText(/protocol:/i)).toBeTruthy()
    expect(screen.getAllByText(/protocol guardrail timeline/i).length).toBeGreaterThan(0)
    expect(screen.getByText(/review sop guidance/i)).toBeTruthy()
    expect(screen.getAllByText(/recovery drill/i).length).toBeGreaterThan(0)
  })
})
