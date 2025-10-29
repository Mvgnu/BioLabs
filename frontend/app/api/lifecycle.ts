'use client'

// purpose: lifecycle narrative API client helpers
// status: experimental

import api from './client'
import type { LifecycleScope, LifecycleTimelineResponse } from '../types'

export const getLifecycleTimeline = async (
  scope: LifecycleScope,
  options?: { limit?: number },
): Promise<LifecycleTimelineResponse> => {
  const params = new URLSearchParams()
  if (options?.limit) {
    params.set('limit', String(options.limit))
  }
  for (const [key, value] of Object.entries(scope)) {
    if (!value) continue
    params.set(key, value)
  }
  if (params.keys().next().done) {
    throw new Error('At least one lifecycle scope identifier must be provided')
  }
  const query = params.toString()
  const response = await api.get<LifecycleTimelineResponse>(
    `/api/lifecycle/timeline${query ? `?${query}` : ''}`,
  )
  return response.data
}

