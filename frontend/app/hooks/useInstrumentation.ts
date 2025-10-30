'use client'

import { useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import api from '../api/client'
import type {
  InstrumentProfile,
  InstrumentRun,
  InstrumentRunTelemetryEnvelope,
  InstrumentSimulationEvent,
  InstrumentSimulationResult,
} from '../types'

// purpose: provide instrumentation data fetching, simulation triggers, and telemetry hydration hooks
// status: experimental

const profileKey = ['instrumentation', 'profiles'] as const

export const useInstrumentProfiles = (teamId?: string | null) => {
  return useQuery({
    queryKey: teamId ? [...profileKey, teamId] : profileKey,
    queryFn: async () => {
      const query = teamId ? `?team_id=${teamId}` : ''
      const resp = await api.get(`/api/instrumentation/instruments${query}`)
      return resp.data as InstrumentProfile[]
    },
  })
}

export const useInstrumentRuns = (equipmentId: string | null) => {
  return useQuery({
    queryKey: ['instrumentation', 'runs', equipmentId],
    queryFn: async () => {
      if (!equipmentId) {
        return [] as InstrumentRun[]
      }
      const resp = await api.get(`/api/instrumentation/runs?equipment_id=${equipmentId}`)
      return resp.data as InstrumentRun[]
    },
    enabled: Boolean(equipmentId),
  })
}

export const useInstrumentRunEnvelope = (runId: string | null) => {
  return useQuery({
    queryKey: ['instrumentation', 'envelopes', runId],
    queryFn: async () => {
      if (!runId) {
        return null
      }
      const resp = await api.get(`/api/instrumentation/runs/${runId}/telemetry`)
      return resp.data as InstrumentRunTelemetryEnvelope
    },
    enabled: Boolean(runId),
    refetchInterval: 5000,
  })
}

type SimulationOptions = {
  equipmentId: string
}

export const useSimulateRun = ({ equipmentId }: SimulationOptions) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: Partial<{ team_id: string; scenario: string; run_parameters: Record<string, any>; duration_minutes: number }>) => {
      const resp = await api.post(`/api/instrumentation/instruments/${equipmentId}/simulate`, data)
      return resp.data as InstrumentSimulationResult
    },
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: profileKey })
      qc.invalidateQueries({ queryKey: ['instrumentation', 'runs', equipmentId] })
      qc.setQueryData(['instrumentation', 'envelopes', result.run.id], result.envelope)
    },
  })
}

export const useSimulationEventStream = (
  initialEvents: InstrumentSimulationEvent[] | undefined,
  latestEnvelope: InstrumentRunTelemetryEnvelope | null,
) => {
  const eventsRef = useRef<InstrumentSimulationEvent[]>(initialEvents ?? [])

  // purpose: maintain stable simulation timeline list for client visualizations
  // status: experimental
  useEffect(() => {
    const baseEvents = initialEvents ?? []
    if (!latestEnvelope) {
      eventsRef.current = [...baseEvents]
      return
    }
    const telemetryEvents = latestEnvelope.samples.map((sample, index) => ({
      sequence: index + 1,
      event_type: 'telemetry' as const,
      recorded_at: sample.recorded_at,
      payload: {
        channel: sample.channel,
        payload: sample.payload,
      },
    }))
    const merged = [...telemetryEvents, ...baseEvents.filter((event) => event.event_type === 'status')]
    merged.sort((a, b) => new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime())
    merged.forEach((event, index) => {
      event.sequence = index + 1
    })
    eventsRef.current = merged
  }, [initialEvents, latestEnvelope])

  return eventsRef.current
}
