// purpose: axios helpers for cloning planner orchestration endpoints
// status: experimental

import api from './client'
import type {
  CloningPlannerCancelPayload,
  CloningPlannerFinalizePayload,
  CloningPlannerResumePayload,
  CloningPlannerSequenceInput,
  CloningPlannerSession,
  CloningPlannerStagePayload,
} from '../types'

export interface CreateCloningPlannerSessionPayload {
  assembly_strategy: string
  input_sequences: CloningPlannerSequenceInput[]
  metadata?: Record<string, any>
}

export const createCloningPlannerSession = async (
  payload: CreateCloningPlannerSessionPayload,
): Promise<CloningPlannerSession> => {
  const response = await api.post('/api/cloning-planner/sessions', payload)
  return response.data as CloningPlannerSession
}

export const getCloningPlannerSession = async (
  sessionId: string,
): Promise<CloningPlannerSession> => {
  const response = await api.get(`/api/cloning-planner/sessions/${sessionId}`)
  return response.data as CloningPlannerSession
}

export const submitCloningPlannerStage = async (
  sessionId: string,
  stage: string,
  payload: CloningPlannerStagePayload,
): Promise<CloningPlannerSession> => {
  const response = await api.post(
    `/api/cloning-planner/sessions/${sessionId}/steps/${stage}`,
    payload,
  )
  return response.data as CloningPlannerSession
}

export const resumeCloningPlannerSession = async (
  sessionId: string,
  payload: CloningPlannerResumePayload,
): Promise<CloningPlannerSession> => {
  const response = await api.post(
    `/api/cloning-planner/sessions/${sessionId}/resume`,
    payload,
  )
  return response.data as CloningPlannerSession
}

export const finalizeCloningPlannerSession = async (
  sessionId: string,
  payload: CloningPlannerFinalizePayload,
): Promise<CloningPlannerSession> => {
  const response = await api.post(
    `/api/cloning-planner/sessions/${sessionId}/finalize`,
    payload,
  )
  return response.data as CloningPlannerSession
}

export const cancelCloningPlannerSession = async (
  sessionId: string,
  payload: CloningPlannerCancelPayload,
): Promise<CloningPlannerSession> => {
  const response = await api.post(
    `/api/cloning-planner/sessions/${sessionId}/cancel`,
    payload,
  )
  return response.data as CloningPlannerSession
}
