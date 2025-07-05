'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import type { Lab, LabConnection } from '../types'

export const useLabs = () => {
  return useQuery({
    queryKey: ['labs'],
    queryFn: async () => {
      const resp = await api.get('/api/labs')
      return resp.data as Lab[]
    },
  })
}

export const useCreateLab = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: any) => api.post('/api/labs', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['labs'] }),
  })
}

export const useConnections = () => {
  return useQuery({
    queryKey: ['lab-connections'],
    queryFn: async () => {
      const resp = await api.get('/api/labs/connections')
      return resp.data as LabConnection[]
    },
  })
}

export const useRequestConnection = (labId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (target_lab: string) =>
      api.post(`/api/labs/${labId}/connections`, { target_lab }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['lab-connections'] }),
  })
}

export const useAcceptConnection = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      api.post(`/api/labs/connections/${id}/accept`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['lab-connections'] }),
  })
}
