'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { governanceApi } from '../api/governance'
import type { CustodyLogCreate, FreezerFaultCreate } from '../types'

// purpose: expose custody governance data hooks for freezer dashboards and ledgers
// status: pilot

export const useCustodyFreezers = (teamId?: string | null) => {
  return useQuery({
    queryKey: ['governance', 'custody', 'freezers', teamId ?? 'all'],
    queryFn: () =>
      governanceApi.getCustodyFreezers(
        teamId ? { team_id: teamId } : undefined,
      ),
    staleTime: 60 * 1000,
  })
}

export interface CustodyLogFilters {
  assetId?: string | null
  assetVersionId?: string | null
  plannerSessionId?: string | null
  protocolExecutionId?: string | null
  executionEventId?: string | null
  compartmentId?: string | null
  limit?: number | null
}

export const useCustodyLogs = (filters?: CustodyLogFilters) => {
  const key = [
    'governance',
    'custody',
    'logs',
    filters?.assetId ?? null,
    filters?.assetVersionId ?? null,
    filters?.plannerSessionId ?? null,
    filters?.protocolExecutionId ?? null,
    filters?.executionEventId ?? null,
    filters?.compartmentId ?? null,
    filters?.limit ?? null,
  ]
  return useQuery({
    queryKey: key,
    queryFn: () =>
      governanceApi.listCustodyLogs({
        asset_id: filters?.assetId ?? undefined,
        asset_version_id: filters?.assetVersionId ?? undefined,
        planner_session_id: filters?.plannerSessionId ?? undefined,
        protocol_execution_id: filters?.protocolExecutionId ?? undefined,
        execution_event_id: filters?.executionEventId ?? undefined,
        compartment_id: filters?.compartmentId ?? undefined,
        limit: filters?.limit ?? undefined,
      }),
    staleTime: 30 * 1000,
  })
}

export const useCreateCustodyLog = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: CustodyLogCreate) => governanceApi.createCustodyLog(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['governance', 'custody', 'logs'] })
      qc.invalidateQueries({ queryKey: ['governance', 'custody', 'freezers'] })
      qc.invalidateQueries({ queryKey: ['governance', 'custody', 'escalations'] })
      qc.invalidateQueries({ queryKey: ['governance', 'custody', 'faults'] })
    },
  })
}

export interface CustodyEscalationFilters {
  teamId?: string | null
  status?: string[] | null
  protocolExecutionId?: string | null
  executionEventId?: string | null
}

export const useCustodyEscalations = (filters?: CustodyEscalationFilters) => {
  const key = [
    'governance',
    'custody',
    'escalations',
    filters?.teamId ?? null,
    filters?.status ? filters.status.join(',') : null,
    filters?.protocolExecutionId ?? null,
    filters?.executionEventId ?? null,
  ]
  return useQuery({
    queryKey: key,
    queryFn: () =>
      governanceApi.listCustodyEscalations({
        team_id: filters?.teamId ?? undefined,
        status: filters?.status ?? undefined,
        protocol_execution_id: filters?.protocolExecutionId ?? undefined,
        execution_event_id: filters?.executionEventId ?? undefined,
      }),
    staleTime: 15 * 1000,
  })
}

export const useAcknowledgeCustodyEscalation = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (escalationId: string) => governanceApi.acknowledgeCustodyEscalation(escalationId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['governance', 'custody', 'escalations'] })
    },
  })
}

export const useResolveCustodyEscalation = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (escalationId: string) => governanceApi.resolveCustodyEscalation(escalationId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['governance', 'custody', 'escalations'] })
    },
  })
}

export const useTriggerCustodyEscalationNotification = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (escalationId: string) => governanceApi.notifyCustodyEscalation(escalationId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['governance', 'custody', 'escalations'] })
    },
  })
}

export interface FreezerFaultFilters {
  teamId?: string | null
  includeResolved?: boolean
}

export const useFreezerFaults = (filters?: FreezerFaultFilters) => {
  const key = [
    'governance',
    'custody',
    'faults',
    filters?.teamId ?? null,
    filters?.includeResolved ?? false,
  ]
  return useQuery({
    queryKey: key,
    queryFn: () =>
      governanceApi.listFreezerFaults({
        team_id: filters?.teamId ?? undefined,
        include_resolved: filters?.includeResolved ?? undefined,
      }),
    staleTime: 30 * 1000,
  })
}

interface FreezerFaultMutationPayload {
  freezerId: string
  payload: FreezerFaultCreate
}

export const useCreateFreezerFault = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ freezerId, payload }: FreezerFaultMutationPayload) =>
      governanceApi.createFreezerFault(freezerId, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['governance', 'custody', 'faults'] })
    },
  })
}

export const useResolveFreezerFault = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (faultId: string) => governanceApi.resolveFreezerFault(faultId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['governance', 'custody', 'faults'] })
    },
  })
}
