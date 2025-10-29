'use client'

// purpose: fetch aggregated lifecycle timelines via React Query
// status: experimental

import { useMemo } from 'react'
import { useQuery, type UseQueryResult } from '@tanstack/react-query'

import { getLifecycleTimeline } from '../api/lifecycle'
import type { LifecycleScope, LifecycleTimelineResponse } from '../types'

export interface UseLifecycleNarrativeOptions {
  enabled?: boolean
  limit?: number
}

const serializeScope = (scope: LifecycleScope): string => {
  const entries = Object.entries(scope)
    .filter(([, value]) => Boolean(value))
    .sort(([aKey], [bKey]) => aKey.localeCompare(bKey))
  return JSON.stringify(entries)
}

export const useLifecycleNarrative = (
  scope: LifecycleScope,
  options?: UseLifecycleNarrativeOptions,
): UseQueryResult<LifecycleTimelineResponse> => {
  const queryKey = useMemo(() => {
    return [
      'lifecycle',
      'timeline',
      serializeScope(scope),
      options?.limit ?? null,
    ]
  }, [scope, options?.limit])

  const enabled = useMemo(() => {
    return (
      options?.enabled !== false &&
      Object.values(scope).some((value) => Boolean(value))
    )
  }, [scope, options?.enabled])

  return useQuery({
    queryKey,
    queryFn: () => getLifecycleTimeline(scope, { limit: options?.limit }),
    enabled,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  })
}

