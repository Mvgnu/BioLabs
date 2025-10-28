'use client'

import { useEffect, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import type {
  GovernanceDecisionTimelineEntry,
  GovernanceDecisionTimelinePage,
  GovernanceOverrideLiveState,
} from '../types'

type GovernanceStreamOptions = {
  pageSize?: number
  eventSourceFactory?: (url: string) => EventSource
}

type GovernanceStreamSnapshotEvent = {
  type: 'snapshot'
  execution_id: string
  locks: GovernanceOverrideLiveState[]
}

type GovernanceStreamLockEvent = {
  type: 'lock_event'
  execution_id: string
  override_id: string
  lock_state: GovernanceOverrideLiveState
}

type GovernanceStreamCooldownTick = {
  type: 'cooldown_tick'
  execution_id: string
  cooldowns: { override_id: string; remaining_seconds: number; expires_at?: string | null }[]
}

type GovernanceStreamPayload =
  | GovernanceStreamSnapshotEvent
  | GovernanceStreamLockEvent
  | GovernanceStreamCooldownTick

type GovernanceTimelineQueryKey = [string, string, string | null, number?]

const cloneLiveState = (state: GovernanceOverrideLiveState): GovernanceOverrideLiveState => ({
  ...state,
  lock: state.lock ? { ...state.lock, actor: state.lock.actor ? { ...state.lock.actor } : null } : null,
  cooldown: state.cooldown ? { ...state.cooldown } : null,
})

const extractOverrideKeys = (entry: GovernanceDecisionTimelineEntry) => {
  const detail = entry.detail ?? {}
  const nested = typeof detail.detail === 'object' ? (detail.detail as Record<string, any>) : detail
  const overrideId =
    nested?.override_id ?? detail?.override_id ?? entry.detail?.override_id ?? entry.live_state?.override_id ?? null
  const executionHash =
    nested?.execution_hash ?? detail?.execution_hash ?? entry.detail?.execution_hash ?? entry.live_state?.execution_hash ?? null
  const recommendationId =
    detail?.recommendation_id ?? nested?.recommendation_id ?? entry.detail?.recommendation_id ?? entry.rule_key ?? null
  return { overrideId, executionHash, recommendationId }
}

const updateTimelinePage = (
  page: GovernanceDecisionTimelinePage | undefined,
  lookup: (keys: ReturnType<typeof extractOverrideKeys>) => GovernanceOverrideLiveState | null,
): GovernanceDecisionTimelinePage | undefined => {
  if (!page) return page
  let mutated = false
  const entries = page.entries.map((entry) => {
    if (entry.entry_type !== 'override_action') {
      if (entry.live_state) {
        mutated = true
        return { ...entry, live_state: null }
      }
      return entry
    }
    const state = lookup(extractOverrideKeys(entry))
    if (!state) {
      if (entry.live_state) {
        mutated = true
        return { ...entry, live_state: null }
      }
      return entry
    }
    mutated = true
    return { ...entry, live_state: cloneLiveState(state) }
  })
  return mutated ? { ...page, entries } : page
}

export const useGovernanceStream = (
  executionId: string | null,
  options?: GovernanceStreamOptions,
) => {
  const queryClient = useQueryClient()
  const stateRef = useRef(new Map<string, GovernanceOverrideLiveState>())
  const hashIndexRef = useRef(new Map<string, string>())
  const recommendationIndexRef = useRef(new Map<string, string>())
  const sourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!executionId || typeof window === 'undefined') {
      return
    }

    const stateMap = stateRef.current
    const hashIndex = hashIndexRef.current
    const recommendationIndex = recommendationIndexRef.current

    stateMap.clear()
    hashIndex.clear()
    recommendationIndex.clear()

    const applyToQueries = () => {
      const queries = queryClient
        .getQueryCache()
        .findAll({
          predicate: (query) => {
            const key = query.queryKey as GovernanceTimelineQueryKey
            return (
              Array.isArray(key) &&
              key[0] === 'experiment-console' &&
              key[1] === 'governance-timeline' &&
              key[2] === executionId
            )
          },
        })

      for (const query of queries) {
        queryClient.setQueryData<GovernanceDecisionTimelinePage | undefined>(
          query.queryKey,
          (existing) => updateTimelinePage(existing, (keys) => {
            if (keys.overrideId && stateMap.has(keys.overrideId)) {
              return stateMap.get(keys.overrideId) ?? null
            }
            if (keys.executionHash && hashIndex.has(keys.executionHash)) {
              const overrideId = hashIndex.get(keys.executionHash)
              return overrideId ? stateMap.get(overrideId) ?? null : null
            }
            if (keys.recommendationId && recommendationIndex.has(keys.recommendationId)) {
              const overrideId = recommendationIndex.get(keys.recommendationId)
              return overrideId ? stateMap.get(overrideId) ?? null : null
            }
            return null
          }),
        )
      }
    }

    const persistState = (state: GovernanceOverrideLiveState) => {
      const cloned = cloneLiveState(state)
      stateMap.set(cloned.override_id, cloned)
      if (cloned.execution_hash) {
        hashIndex.set(cloned.execution_hash, cloned.override_id)
      }
      if (cloned.recommendation_id) {
        recommendationIndex.set(cloned.recommendation_id, cloned.override_id)
      }
    }

    const handlePayload = (payload: GovernanceStreamPayload) => {
      if (payload.execution_id && payload.execution_id !== executionId) {
        return
      }
      if (payload.type === 'snapshot') {
        stateMap.clear()
        hashIndex.clear()
        recommendationIndex.clear()
        payload.locks.forEach((state) => persistState(state))
        applyToQueries()
        return
      }
      if (payload.type === 'lock_event') {
        persistState(payload.lock_state)
        applyToQueries()
        return
      }
      if (payload.type === 'cooldown_tick') {
        let mutated = false
        payload.cooldowns.forEach((cooldown) => {
          if (!stateMap.has(cooldown.override_id)) {
            return
          }
          const current = stateMap.get(cooldown.override_id)
          if (!current) return
          const nextState: GovernanceOverrideLiveState = {
            ...current,
            cooldown: {
              ...(current.cooldown ?? {}),
              expires_at: cooldown.expires_at ?? current.cooldown?.expires_at ?? null,
              remaining_seconds: cooldown.remaining_seconds,
            },
          }
          persistState(nextState)
          mutated = true
        })
        if (mutated) {
          applyToQueries()
        }
      }
    }

    const buildUrl = () => {
      const url = new URL('/api/experiment-console/governance/timeline/stream', window.location.origin)
      url.searchParams.set('execution_id', executionId)
      if (options?.pageSize) {
        url.searchParams.set('limit', String(options.pageSize))
      }
      return url.toString()
    }

    const createSource = options?.eventSourceFactory ?? ((target: string) => new EventSource(target))
    const source = createSource(buildUrl())
    sourceRef.current = source

    source.onmessage = (event) => {
      if (!event.data) return
      try {
        const payload = JSON.parse(event.data) as GovernanceStreamPayload
        handlePayload(payload)
      } catch (error) {
        // silently ignore malformed frames
      }
    }

    source.onerror = () => {
      source.close()
    }

    return () => {
      stateMap.clear()
      hashIndex.clear()
      recommendationIndex.clear()
      if (sourceRef.current) {
        sourceRef.current.close()
        sourceRef.current = null
      }
    }
  }, [executionId, options?.eventSourceFactory, options?.pageSize, queryClient])
}
