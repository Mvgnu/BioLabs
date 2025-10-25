'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import type {
  ExperimentExecutionSession,
  ExperimentExecutionSessionCreate,
  ExperimentStepStatusUpdate,
} from '../types'

const sessionKey = (executionId: string | null) => [
  'experiment-console',
  'sessions',
  executionId,
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
