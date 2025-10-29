import { render, screen } from '@testing-library/react'
import React from 'react'
import { describe, expect, it } from 'vitest'
import CustodyFreezerMap from '../CustodyFreezerMap'
import type { CustodyCompartmentNode, CustodyFreezerUnit } from '../../../types'

const buildNode = (
  overrides: Partial<CustodyCompartmentNode> = {},
): CustodyCompartmentNode => ({
  id: 'compartment-1',
  label: 'Rack A1',
  position_index: 0,
  capacity: 10,
  guardrail_thresholds: {},
  occupancy: 4,
  guardrail_flags: [],
  latest_activity_at: new Date().toISOString(),
  children: [],
  ...overrides,
})

const buildUnit = (overrides: Partial<CustodyFreezerUnit> = {}): CustodyFreezerUnit => ({
  id: 'unit-1',
  name: 'Freezer Alpha',
  status: 'active',
  facility_code: 'HQ-1',
  guardrail_config: {},
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  compartments: [buildNode()],
  ...overrides,
})

describe('CustodyFreezerMap', () => {
  it('renders loading state', () => {
    render(<CustodyFreezerMap units={undefined} isLoading error={null} />)
    expect(screen.getByRole('heading', { name: /loading freezer topology/i })).toBeTruthy()
  })

  it('renders empty state when no units provided', () => {
    render(<CustodyFreezerMap units={[]} isLoading={false} error={null} />)
    expect(screen.getByText(/no freezer units registered/i)).toBeTruthy()
  })

  it('renders guardrail badges for flagged compartments', () => {
    const unit = buildUnit({
      compartments: [
        buildNode({
          guardrail_flags: ['capacity.exceeded'],
        }),
      ],
    })
    render(<CustodyFreezerMap units={[unit]} isLoading={false} error={null} />)
    expect(screen.getByText('Freezer Alpha')).toBeTruthy()
    expect(screen.getByText('capacity.exceeded')).toBeTruthy()
  })
})
