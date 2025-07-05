'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import type { NotebookEntry } from '../types'

export const useNotebookEntries = () => {
  return useQuery({
    queryKey: ['notebook'],
    queryFn: async () => {
      const resp = await api.get('/api/notebook/entries')
      return resp.data as NotebookEntry[]
    },
  })
}

export const useCreateEntry = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: any) => api.post('/api/notebook/entries', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notebook'] }),
  })
}

export const useUpdateEntry = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: string; data: any }) =>
      api.put(`/api/notebook/entries/${vars.id}`, vars.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notebook'] }),
  })
}

export const useDeleteEntry = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete(`/api/notebook/entries/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notebook'] }),
  })
}
