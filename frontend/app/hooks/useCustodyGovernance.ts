'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { governanceApi } from '../api/governance'
import type { CustodyLogCreate } from '../types'

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
    },
  })
}
