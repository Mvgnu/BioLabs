'use client'

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import api from '../api/client'
import type {
  ExperimentExecutionSession,
  ExperimentExecutionSessionCreate,
  ExperimentRemediationRequest,
  ExperimentRemediationResponse,
  ExperimentStepStatusUpdate,
  ExperimentTimelinePage,
} from '../types'

const sessionKey = (executionId: string | null) => [
  'experiment-console',
  'sessions',
  executionId,
]

const timelineKey = (
  executionId: string | null,
  filters?: { eventTypes?: string[] },
) => [
  'experiment-console',
  'timeline',
  executionId,
  filters?.eventTypes?.slice().sort().join(','),
]

export const useExperimentSession = (executionId: string | null) => {
  return useQuery({
    queryKey: sessionKey(executionId),
    enabled: Boolean(executionId),
    queryFn: async () => {
      const resp = await api.get(`/api/experiment-console/sessions/${executionId}`)
      return resp.data as ExperimentExecutionSession
    },
  })
}

export const useCreateExperimentSession = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: ExperimentExecutionSessionCreate) => {
      const resp = await api.post('/api/experiment-console/sessions', payload)
      return resp.data as ExperimentExecutionSession
    },
    onSuccess: (data) => {
      qc.setQueryData(sessionKey(data.execution.id), data)
    },
  })
}

export const useUpdateExperimentStep = (executionId: string | null) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: { stepIndex: number; update: ExperimentStepStatusUpdate }) => {
      if (!executionId) {
        throw new Error('Execution id required for step updates')
      }
      const resp = await api.post(
        `/api/experiment-console/sessions/${executionId}/steps/${vars.stepIndex}`,
        vars.update,
      )
      return resp.data as ExperimentExecutionSession
    },
    onSuccess: (data) => {
      qc.setQueryData(sessionKey(executionId), data)
    },
  })
}

export const useAdvanceExperimentStep = (executionId: string | null) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: { stepIndex: number }) => {
      if (!executionId) {
        throw new Error('Execution id required for orchestration advance')
      }
      const resp = await api.post(
        `/api/experiment-console/sessions/${executionId}/steps/${vars.stepIndex}/advance`,
        {},
      )
      return resp.data as ExperimentExecutionSession
    },
    onSuccess: (data) => {
      qc.setQueryData(sessionKey(executionId), data)
    },
  })
}

export const useRemediateExperimentStep = (executionId: string | null) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: {
      stepIndex: number
      request?: ExperimentRemediationRequest
    }) => {
      if (!executionId) {
        throw new Error('Execution id required for remediation')
      }
      const resp = await api.post(
        `/api/experiment-console/sessions/${executionId}/steps/${vars.stepIndex}/remediate`,
        vars.request ?? {},
      )
      return resp.data as ExperimentRemediationResponse
    },
    onSuccess: (data) => {
      qc.setQueryData(sessionKey(executionId), data.session)
    },
  })
}

export const useExecutionTimeline = (
  executionId: string | null,
  filters?: { eventTypes?: string[]; pageSize?: number },
) => {
  const pageSize = Math.min(Math.max(filters?.pageSize ?? 50, 1), 200)
  return useInfiniteQuery({
    queryKey: timelineKey(executionId, filters),
    enabled: Boolean(executionId),
    queryFn: async ({ pageParam }): Promise<ExperimentTimelinePage> => {
      if (!executionId) {
        throw new Error('Execution id required for timeline queries')
      }
      const params: Record<string, any> = { limit: pageSize }
      if (pageParam) {
        params.cursor = pageParam
      }
      if (filters?.eventTypes?.length) {
        params.event_types = filters.eventTypes.join(',')
      }
      const resp = await api.get(
        `/api/experiment-console/sessions/${executionId}/timeline`,
        { params },
      )
      return resp.data as ExperimentTimelinePage
    },
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  })
}
