'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import type { FieldDefinition } from '../types'

export const useFieldDefinitions = (entity: string) => {
  return useQuery({
    queryKey: ['fields', entity],
    queryFn: async () => {
      const resp = await api.get(`/api/fields/definitions/${entity}`)
      return resp.data as FieldDefinition[]
    },
  })
}

export const useCreateField = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: any) => api.post('/api/fields/definitions', data),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ['fields', vars.entity_type] })
    },
  })
}

export const useDeleteField = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: string; entity: string }) =>
      api.delete(`/api/fields/definitions/${vars.id}`),
    onSuccess: (_d, vars) => {
      qc.invalidateQueries({ queryKey: ['fields', vars.entity] })
    },
  })
}
