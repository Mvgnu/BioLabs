'use client'

// purpose: subscribe to cloning planner orchestration state and expose mutation helpers
// status: experimental

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
} from '@tanstack/react-query'

import {
  cancelCloningPlannerSession,
  finalizeCloningPlannerSession,
  getCloningPlannerSession,
  resumeCloningPlannerSession,
  submitCloningPlannerStage,
} from '../api/cloningPlanner'
import api from '../api/client'
import type {
  CloningPlannerCancelPayload,
  CloningPlannerEventPayload,
  CloningPlannerFinalizePayload,
  CloningPlannerMitigationHint,
  CloningPlannerDrillSummary,
  CloningPlannerRecoveryBundle,
  CloningPlannerResumePayload,
  CloningPlannerResumeToken,
  CloningPlannerSession,
  CloningPlannerStagePayload,
  CloningPlannerStageRecord,
} from '../types'

const STREAM_PATH = (sessionId: string) => `/api/cloning-planner/sessions/${sessionId}/events`

const shouldInvalidate = (eventType: string): boolean => {
  return [
    'session_created',
    'stage_started',
    'stage_completed',
    'stage_failed',
    'session_finalized',
    'guardrail_hold',
  ].includes(eventType)
}

export interface UseCloningPlannerOptions {
  eventSourceFactory?: (url: string) => EventSource
}

export interface UseCloningPlannerResult {
  data: CloningPlannerSession | undefined
  isLoading: boolean
  isFetching: boolean
  error: unknown
  events: CloningPlannerEventPayload[]
  replayWindow: CloningPlannerStageRecord[]
  comparisonWindow: CloningPlannerStageRecord[]
  latestResumeToken: CloningPlannerResumeToken | null
  recoveryBundle: CloningPlannerRecoveryBundle | null
  mitigationHints: CloningPlannerMitigationHint[]
  refetch: () => Promise<CloningPlannerSession | undefined>
  runStage: (stage: string, payload: CloningPlannerStagePayload) => Promise<CloningPlannerSession>
  resume: (payload: CloningPlannerResumePayload) => Promise<CloningPlannerSession>
  finalize: (payload: CloningPlannerFinalizePayload) => Promise<CloningPlannerSession>
  cancel: (payload: CloningPlannerCancelPayload) => Promise<CloningPlannerSession>
  mutations: {
    stage: UseMutationResult<
      CloningPlannerSession,
      unknown,
      { stage: string; payload: CloningPlannerStagePayload },
      unknown
    >
    resume: UseMutationResult<CloningPlannerSession, unknown, CloningPlannerResumePayload, unknown>
    finalize: UseMutationResult<CloningPlannerSession, unknown, CloningPlannerFinalizePayload, unknown>
    cancel: UseMutationResult<CloningPlannerSession, unknown, CloningPlannerCancelPayload, unknown>
  }
}

const resolveStreamUrl = (sessionId: string): string => {
  const base = (api.defaults?.baseURL as string | undefined) ?? ''
  const trimmed = base.endsWith('/') ? base.slice(0, -1) : base
  const path = STREAM_PATH(sessionId)
  if (!trimmed) {
    return path
  }
  return `${trimmed}${path}`
}

export const useCloningPlanner = (
  sessionId: string | null,
  options?: UseCloningPlannerOptions,
): UseCloningPlannerResult => {
  const queryClient = useQueryClient()
  const [events, setEvents] = useState<CloningPlannerEventPayload[]>([])
  const [replayWindow, setReplayWindow] = useState<CloningPlannerStageRecord[]>([])
  const [comparisonWindow, setComparisonWindow] = useState<CloningPlannerStageRecord[]>([])
  const [recoveryBundle, setRecoveryBundle] = useState<CloningPlannerRecoveryBundle | null>(null)
  const streamFactoryRef = useRef(options?.eventSourceFactory)
  const streamUrl = useMemo(() => (sessionId ? resolveStreamUrl(sessionId) : null), [sessionId])

  useEffect(() => {
    streamFactoryRef.current = options?.eventSourceFactory
  }, [options?.eventSourceFactory])

  useEffect(() => {
    if (!sessionId || !streamUrl || typeof window === 'undefined') {
      return undefined
    }

    const factory = streamFactoryRef.current ?? ((target: string) => new EventSource(target))
    const source = factory(streamUrl)

    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as CloningPlannerEventPayload
        if (Array.isArray(payload.replay_window)) {
          setReplayWindow(payload.replay_window as CloningPlannerStageRecord[])
        }
        if (Array.isArray(payload.comparison_window)) {
          setComparisonWindow(payload.comparison_window as CloningPlannerStageRecord[])
        }
        if (payload.recovery_bundle) {
          const bundle = payload.recovery_bundle as CloningPlannerRecoveryBundle
          const drillSummaries = Array.isArray(bundle.drill_summaries)
            ? (bundle.drill_summaries as CloningPlannerDrillSummary[])
            : ((payload.drill_summaries as CloningPlannerDrillSummary[] | undefined) ?? [])
          setRecoveryBundle({ ...bundle, drill_summaries: drillSummaries })
        } else if (Array.isArray(payload.drill_summaries)) {
          setRecoveryBundle((previous) => {
            if (!previous) {
              return previous
            }
            return { ...previous, drill_summaries: payload.drill_summaries as CloningPlannerDrillSummary[] }
          })
        }
        setEvents((previous) => {
          const next = [...previous, payload]
          return next.length > 50 ? next.slice(next.length - 50) : next
        })
        if (shouldInvalidate(payload.type)) {
          queryClient.invalidateQueries({ queryKey: ['cloning-planner', 'session', sessionId] }).catch(() => {})
        }
      } catch (error) {
        console.warn('Failed to parse cloning planner event', error)
      }
    }

    source.onerror = () => {
      source.close()
    }

    return () => {
      source.close()
    }
  }, [sessionId, streamUrl, queryClient])

  const fetchSession = useCallback(async (): Promise<CloningPlannerSession> => {
    if (!sessionId) {
      throw new Error('sessionId is required')
    }
    return getCloningPlannerSession(sessionId)
  }, [sessionId])

  const query = useQuery({
    queryKey: ['cloning-planner', 'session', sessionId],
    queryFn: fetchSession,
    enabled: Boolean(sessionId),
    refetchOnWindowFocus: false,
  })

  useEffect(() => {
    if (query.data?.recovery_bundle) {
      const bundle = query.data.recovery_bundle
      const drillSummaries = Array.isArray(bundle.drill_summaries)
        ? (bundle.drill_summaries as CloningPlannerDrillSummary[])
        : ((query.data.drill_summaries as CloningPlannerDrillSummary[] | undefined) ?? [])
      setRecoveryBundle({ ...bundle, drill_summaries: drillSummaries })
    } else if (Array.isArray(query.data?.drill_summaries)) {
      setRecoveryBundle((previous) => {
        if (!previous) {
          return previous
        }
        return {
          ...previous,
          drill_summaries: query.data?.drill_summaries as CloningPlannerDrillSummary[],
        }
      })
    } else if (query.data && !query.data.recovery_bundle) {
      setRecoveryBundle(null)
    }
  }, [query.data, query.data?.recovery_bundle, query.data?.drill_summaries])

  const stageMutation = useMutation<
    CloningPlannerSession,
    unknown,
    { stage: string; payload: CloningPlannerStagePayload }
  >({
    mutationFn: async ({
      stage,
      payload,
    }: {
      stage: string
      payload: CloningPlannerStagePayload
    }) => {
      if (!sessionId) {
        throw new Error('sessionId is required')
      }
      return submitCloningPlannerStage(sessionId, stage, payload)
    },
    onSuccess: (data) => {
      queryClient.setQueryData(['cloning-planner', 'session', sessionId], data)
    },
  })

  const resumeMutation = useMutation<
    CloningPlannerSession,
    unknown,
    CloningPlannerResumePayload
  >({
    mutationFn: async (payload: CloningPlannerResumePayload) => {
      if (!sessionId) {
        throw new Error('sessionId is required')
      }
      return resumeCloningPlannerSession(sessionId, payload)
    },
    onSuccess: (data) => {
      queryClient.setQueryData(['cloning-planner', 'session', sessionId], data)
    },
  })

  const finalizeMutation = useMutation<
    CloningPlannerSession,
    unknown,
    CloningPlannerFinalizePayload
  >({
    mutationFn: async (payload: CloningPlannerFinalizePayload) => {
      if (!sessionId) {
        throw new Error('sessionId is required')
      }
      return finalizeCloningPlannerSession(sessionId, payload)
    },
    onSuccess: (data) => {
      queryClient.setQueryData(['cloning-planner', 'session', sessionId], data)
    },
  })

  const cancelMutation = useMutation<
    CloningPlannerSession,
    unknown,
    CloningPlannerCancelPayload
  >({
    mutationFn: async (payload: CloningPlannerCancelPayload) => {
      if (!sessionId) {
        throw new Error('sessionId is required')
      }
      return cancelCloningPlannerSession(sessionId, payload)
    },
    onSuccess: (data) => {
      queryClient.setQueryData(['cloning-planner', 'session', sessionId], data)
    },
  })

  const runStage = useCallback(
    async (stage: string, payload: CloningPlannerStagePayload) => {
      return stageMutation.mutateAsync({ stage, payload })
    },
    [stageMutation],
  )

  const resume = useCallback(
    async (payload: CloningPlannerResumePayload) => resumeMutation.mutateAsync(payload),
    [resumeMutation],
  )

  const finalize = useCallback(
    async (payload: CloningPlannerFinalizePayload) => finalizeMutation.mutateAsync(payload),
    [finalizeMutation],
  )

  const cancel = useCallback(
    async (payload: CloningPlannerCancelPayload) => cancelMutation.mutateAsync(payload),
    [cancelMutation],
  )

  const latestResumeToken = useMemo(() => {
    const candidates: CloningPlannerResumeToken[] = []
    if (recoveryBundle?.resume_token) {
      candidates.push(recoveryBundle.resume_token)
    }
    for (let index = events.length - 1; index >= 0; index -= 1) {
      const token = events[index]?.resume_token
      if (token) {
        candidates.push(token)
        break
      }
    }
    const history = query.data?.stage_history ?? []
    for (let index = history.length - 1; index >= 0; index -= 1) {
      const token = history[index]?.resume_token
      if (token) {
        candidates.push(token)
        break
      }
    }
    return candidates.length > 0 ? candidates[0] : null
  }, [events, query.data?.stage_history, recoveryBundle?.resume_token])

  const mitigationHints = useMemo(() => {
    const unique = new Map<string, CloningPlannerMitigationHint>()
    const addHint = (hint: CloningPlannerMitigationHint) => {
      const key = `${hint.category}:${hint.action}`
      if (!unique.has(key)) {
        unique.set(key, hint)
      }
    }
    if (recoveryBundle?.mitigation_hints) {
      recoveryBundle.mitigation_hints.forEach((hint) => addHint(hint))
    }
    events.forEach((event) => {
      event.mitigation_hints?.forEach((hint) => addHint(hint))
    })
    ;(query.data?.stage_history ?? []).forEach((record) => {
      record.mitigation_hints?.forEach((hint) => addHint(hint))
    })
    return Array.from(unique.values())
  }, [events, query.data?.stage_history, recoveryBundle?.mitigation_hints])

  return {
    data: query.data,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    events,
    replayWindow,
    comparisonWindow,
    latestResumeToken,
    recoveryBundle,
    mitigationHints,
    refetch: () => query.refetch().then((result) => result.data),
    runStage,
    resume,
    finalize,
    cancel,
    mutations: {
      stage: stageMutation,
      resume: resumeMutation,
      finalize: finalizeMutation,
      cancel: cancelMutation,
    },
  }
}

