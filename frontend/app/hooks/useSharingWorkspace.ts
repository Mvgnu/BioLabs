'use client'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import api from '../api/client'
import type { DNARepository, DNARepositoryTimelineEvent } from '../types'

// purpose: provide guardrail-aware data hooks for the sharing workspace UI
// status: experimental

const repositoryKey = ['sharing', 'repositories'] as const

export const useRepositories = () => {
  return useQuery({
    queryKey: repositoryKey,
    queryFn: async () => {
      const resp = await api.get('/api/sharing/repositories')
      return resp.data as DNARepository[]
    },
  })
}

export const useCreateRepository = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<DNARepository>) => api.post('/api/sharing/repositories', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: repositoryKey }),
  })
}

export const useAddCollaborator = (repositoryId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { user_id: string; role: string }) =>
      api.post(`/api/sharing/repositories/${repositoryId}/collaborators`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: repositoryKey }),
  })
}

export const useCreateRelease = (repositoryId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: any) =>
      api.post(`/api/sharing/repositories/${repositoryId}/releases`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: repositoryKey })
      qc.invalidateQueries({ queryKey: ['sharing', 'timeline', repositoryId] })
    },
  })
}

export const useApproveRelease = (repositoryId: string | null) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: string; data: any }) =>
      api.post(`/api/sharing/releases/${vars.id}/approvals`, vars.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: repositoryKey })
      if (repositoryId) {
        qc.invalidateQueries({ queryKey: ['sharing', 'timeline', repositoryId] })
      }
    },
  })
}

export const useRepositoryTimeline = (repositoryId: string | null) => {
  return useQuery({
    queryKey: ['sharing', 'timeline', repositoryId],
    queryFn: async () => {
      if (!repositoryId) {
        return [] as DNARepositoryTimelineEvent[]
      }
      const resp = await api.get(`/api/sharing/repositories/${repositoryId}/timeline`)
      return resp.data as DNARepositoryTimelineEvent[]
    },
    enabled: Boolean(repositoryId),
  })
}
