'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import type { ProtocolTemplate, ProtocolExecution } from '../types'

export const useProtocolTemplates = () => {
  return useQuery({
    queryKey: ['protocols', 'templates'],
    queryFn: async () => {
      const resp = await api.get('/api/protocols/templates')
      return resp.data as ProtocolTemplate[]
    },
  })
}

export const useCreateTemplate = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: any) => api.post('/api/protocols/templates', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['protocols', 'templates'] }),
  })
}

export const useUpdateTemplate = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: string; data: any }) =>
      api.put(`/api/protocols/templates/${vars.id}`, vars.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['protocols', 'templates'] }),
  })
}

export const useDeleteTemplate = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/protocols/templates/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['protocols', 'templates'] }),
  })
}

export const useProtocolExecutions = () => {
  return useQuery({
    queryKey: ['protocols', 'executions'],
    queryFn: async () => {
      const resp = await api.get('/api/protocols/executions')
      return resp.data as ProtocolExecution[]
    },
  })
}

export const useCreateExecution = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: any) => api.post('/api/protocols/executions', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['protocols', 'executions'] }),
  })
}

export const useUpdateExecution = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: string; data: any }) =>
      api.put(`/api/protocols/executions/${vars.id}`, vars.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['protocols', 'executions'] }),
  })
}

export const useProtocolDiff = (oldId: string | null, newId: string | null) => {
  return useQuery({
    queryKey: ['protocols', 'diff', oldId, newId],
    queryFn: async () => {
      const resp = await api.get('/api/protocols/diff', {
        params: { old_id: oldId, new_id: newId },
      })
      return resp.data.diff as string
    },
    enabled: !!oldId && !!newId,
  })
}
