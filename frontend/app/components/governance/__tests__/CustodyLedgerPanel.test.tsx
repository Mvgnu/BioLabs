import { render, screen } from '@testing-library/react'
import React from 'react'
import { describe, expect, it } from 'vitest'
import CustodyLedgerPanel from '../CustodyLedgerPanel'
import type { CustodyLogEntry } from '../../../types'

const buildLog = (overrides: Partial<CustodyLogEntry> = {}): CustodyLogEntry => ({
  id: 'log-1',
  asset_version_id: 'asset-1',
  planner_session_id: null,
  compartment_id: 'compartment-1',
  custody_action: 'deposit',
  quantity: 2,
  quantity_units: 'vials',
  performed_for_team_id: 'team-1',
  performed_by_id: 'user-1',
  performed_at: new Date().toISOString(),
  created_at: new Date().toISOString(),
  notes: null,
  guardrail_flags: [],
  meta: {},
  ...overrides,
})

describe('CustodyLedgerPanel', () => {
  it('renders empty state when no logs present', () => {
    render(<CustodyLedgerPanel logs={[]} isLoading={false} error={null} />)
    expect(screen.getByText(/no custody movements recorded/i)).toBeTruthy()
  })

  it('renders guardrail flags', () => {
    const log = buildLog({ guardrail_flags: ['capacity.exceeded'], asset_version_id: null })
    render(<CustodyLedgerPanel logs={[log]} isLoading={false} error={null} />)
    expect(screen.getByText(/custody ledger/i)).toBeTruthy()
    expect(screen.getByText('capacity.exceeded')).toBeTruthy()
    expect(screen.getByText(/unlinked/i)).toBeTruthy()
  })
})
