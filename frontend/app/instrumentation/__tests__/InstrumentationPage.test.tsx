import { fireEvent, render, screen } from '@testing-library/react'
import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import InstrumentationDigitalTwinPage from '../page'
import type {
  InstrumentProfile,
  InstrumentReservation,
  InstrumentRunTelemetryEnvelope,
  InstrumentSimulationResult,
} from '../../types'

const mocks = vi.hoisted(() => ({
  useInstrumentProfiles: vi.fn(),
  useInstrumentRuns: vi.fn(),
  useInstrumentRunEnvelope: vi.fn(),
  useSimulateRun: vi.fn(),
  useSimulationEventStream: vi.fn(),
}))

vi.mock('../../hooks/useInstrumentation', () => mocks)

const {
  useInstrumentProfiles: mockUseInstrumentProfiles,
  useInstrumentRuns: mockUseInstrumentRuns,
  useInstrumentRunEnvelope: mockUseInstrumentRunEnvelope,
  useSimulateRun: mockUseSimulateRun,
  useSimulationEventStream: mockUseSimulationEventStream,
} = mocks

describe('InstrumentationDigitalTwinPage', () => {
  const mutate = vi.fn()
  const envelope: InstrumentRunTelemetryEnvelope = {
    run: {
      id: 'run-1',
      reservation_id: 'res-1',
      equipment_id: 'equip-1',
      team_id: 'team-1',
      planner_session_id: null,
      protocol_execution_id: null,
      status: 'completed',
      run_parameters: { set_point: 42 },
      guardrail_flags: [],
      started_at: new Date('2024-01-01T10:00:00Z').toISOString(),
      completed_at: new Date('2024-01-01T10:10:00Z').toISOString(),
      created_at: new Date('2024-01-01T10:00:00Z').toISOString(),
      updated_at: new Date('2024-01-01T10:10:00Z').toISOString(),
    },
    samples: [
      {
        id: 'sample-1',
        run_id: 'run-1',
        channel: 'temperature',
        payload: { value: 72, simulated: true },
        recorded_at: new Date('2024-01-01T10:05:00Z').toISOString(),
      },
    ],
  }

  const reservation: InstrumentReservation = {
    id: 'res-1',
    equipment_id: 'equip-1',
    planner_session_id: null,
    protocol_execution_id: null,
    team_id: 'team-1',
    requested_by_id: 'user-1',
    scheduled_start: new Date('2024-01-01T09:55:00Z').toISOString(),
    scheduled_end: new Date('2024-01-01T10:15:00Z').toISOString(),
    status: 'completed',
    run_parameters: { set_point: 42 },
    guardrail_snapshot: {},
    created_at: new Date('2024-01-01T09:50:00Z').toISOString(),
    updated_at: new Date('2024-01-01T10:10:00Z').toISOString(),
  }

  const simulationResult: InstrumentSimulationResult = {
    reservation,
    run: envelope.run,
    envelope,
    events: [
      {
        sequence: 1,
        event_type: 'telemetry',
        recorded_at: envelope.samples[0].recorded_at,
        payload: { channel: 'temperature', payload: { value: 72 } },
      },
      {
        sequence: 2,
        event_type: 'status',
        recorded_at: envelope.run.completed_at!,
        payload: { status: 'completed', guardrail_flags: [] },
      },
    ],
  }

  const profile: InstrumentProfile = {
    equipment_id: 'equip-1',
    name: 'Incubator A',
    eq_type: 'incubator',
    status: 'ready',
    team_id: 'team-1',
    capabilities: [
      {
        id: 'cap-1',
        equipment_id: 'equip-1',
        capability_key: 'incubation.humidity',
        title: 'Humidity Control',
        parameters: { range: [30, 60] },
        guardrail_requirements: [],
        created_at: new Date('2024-01-01T09:00:00Z').toISOString(),
        updated_at: new Date('2024-01-01T09:00:00Z').toISOString(),
      },
    ],
    sops: [
      {
        sop_id: 'sop-1',
        title: 'Humidity QC',
        version: 2,
        status: 'active',
        effective_at: new Date('2024-01-01T08:00:00Z').toISOString(),
        retired_at: null,
      },
    ],
    next_reservation: null,
    active_run: envelope.run,
    custody_alerts: [],
  }

  beforeEach(() => {
    mutate.mockReset()
    mockUseInstrumentProfiles.mockReturnValue({ data: [profile] })
    mockUseInstrumentRuns.mockReturnValue({ data: [envelope.run] })
    mockUseInstrumentRunEnvelope.mockReturnValue({ data: envelope })
    mockUseSimulateRun.mockReturnValue({ mutate, isPending: false, data: simulationResult })
    mockUseSimulationEventStream.mockReturnValue(simulationResult.events)
  })

  it('renders instrument details and telemetry timeline', () => {
    render(<InstrumentationDigitalTwinPage />)

    expect(screen.getByText('Instrumentation Digital Twin')).toBeDefined()
    expect(screen.getByText('Incubator A')).toBeDefined()
    expect(screen.getByText(/Capabilities 1/)).toBeDefined()
    expect(screen.getByText(/Telemetry Timeline/)).toBeDefined()
    expect(screen.getByText('#1 TELEMETRY')).toBeDefined()
  })

  it('runs simulation when the control button is clicked', () => {
    render(<InstrumentationDigitalTwinPage />)

    const [button] = screen.getAllByRole('button', { name: /run simulation/i })
    fireEvent.click(button)

    expect(mutate).toHaveBeenCalledWith({ scenario: 'thermal_cycle' })
  })
})
