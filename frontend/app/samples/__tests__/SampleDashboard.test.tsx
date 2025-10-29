import { fireEvent, render, screen } from '@testing-library/react'
import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import SampleDashboard from '../components/SampleDashboard'
import type { InventorySampleSummary, SampleDetail } from '../../types'

const mocks = vi.hoisted(() => ({
  useSampleSummaries: vi.fn(),
  useSampleDetail: vi.fn(),
}))

vi.mock('../../hooks/useSamples', () => mocks)

const { useSampleSummaries: mockUseSampleSummaries, useSampleDetail: mockUseSampleDetail } = mocks

describe('SampleDashboard', () => {
  const summaries: InventorySampleSummary[] = [
    {
      id: 'sample-1',
      name: 'Sample One',
      item_type: 'sample',
      team_id: 'team-1',
      custody_state: 'stored',
      custody_snapshot: { last_action: 'deposit' },
      guardrail_flags: ['lineage.required'],
      linked_planner_session_ids: ['planner-1'],
      linked_asset_version_ids: ['asset-1'],
      open_escalations: 0,
      updated_at: new Date('2024-01-01T00:00:00Z').toISOString(),
    },
    {
      id: 'sample-2',
      name: 'Sample Two',
      item_type: 'sample',
      team_id: 'team-2',
      custody_state: 'in_transit',
      custody_snapshot: { last_action: 'withdrawn' },
      guardrail_flags: [],
      linked_planner_session_ids: [],
      linked_asset_version_ids: [],
      open_escalations: 1,
      updated_at: new Date('2024-01-02T00:00:00Z').toISOString(),
    },
  ]

  const detailById: Record<string, SampleDetail> = {
    'sample-1': {
      item: summaries[0],
      recent_logs: [
        {
          id: 'log-1',
          inventory_item_id: 'sample-1',
          custody_action: 'deposit',
          performed_at: new Date('2024-01-01T00:00:00Z').toISOString(),
          created_at: new Date('2024-01-01T00:00:00Z').toISOString(),
          guardrail_flags: ['lineage.required'],
          meta: {},
          notes: 'Stored for sequencing',
        },
      ],
      escalations: [],
    },
    'sample-2': {
      item: summaries[1],
      recent_logs: [
        {
          id: 'log-2',
          inventory_item_id: 'sample-2',
          custody_action: 'withdrawn',
          performed_at: new Date('2024-01-03T00:00:00Z').toISOString(),
          created_at: new Date('2024-01-03T00:00:00Z').toISOString(),
          guardrail_flags: [],
          meta: {},
          notes: 'Handed off to QC',
        },
      ],
      escalations: [
        {
          id: 'esc-1',
          status: 'open',
          severity: 'warning',
          reason: 'Temperature check overdue',
          due_at: new Date('2024-01-04T00:00:00Z').toISOString(),
          acknowledged_at: null,
          resolved_at: null,
          assigned_to_id: null,
          guardrail_flags: ['temperature'],
          notifications: [],
          meta: {},
          log_id: null,
          freezer_unit_id: null,
          compartment_id: null,
          asset_version_id: null,
          protocol_execution_id: null,
          execution_event_id: null,
          protocol_execution: null,
          created_at: new Date('2024-01-03T00:00:00Z').toISOString(),
          updated_at: new Date('2024-01-03T00:00:00Z').toISOString(),
        },
      ],
    },
  }

  beforeEach(() => {
    mockUseSampleSummaries.mockReturnValue({ data: summaries, isLoading: false })
    mockUseSampleDetail.mockImplementation((sampleId: string | null) => ({
      data: sampleId ? detailById[sampleId] : null,
      isLoading: false,
    }))
  })

  it('renders summary table and default detail view', () => {
    render(<SampleDashboard />)

    expect(screen.getByText('Sample custody overview')).toBeDefined()
    expect(screen.getByText('Sample One')).toBeDefined()
    expect(screen.getByText('Sample Two')).toBeDefined()

    expect(screen.getByText('Custody ledger')).toBeDefined()
    expect(screen.getByText('Stored for sequencing')).toBeDefined()
  })

  it('switches detail panel when selecting a different sample', () => {
    render(<SampleDashboard />)

    const secondRow = screen.getAllByTestId('sample-row')[1]
    fireEvent.click(secondRow)

    expect(mockUseSampleDetail).toHaveBeenCalledWith('sample-2')
    expect(screen.getByText('Handed off to QC')).toBeDefined()
    expect(screen.getByText('Temperature check overdue')).toBeDefined()
  })
})
