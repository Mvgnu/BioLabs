'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import type { ComplianceRecord, StatusCount } from '../types'

export const useComplianceRecords = () => {
  return useQuery({
    queryKey: ['compliance', 'records'],
    queryFn: async () => {
      const resp = await api.get('/api/compliance/records')
      return resp.data as ComplianceRecord[]
    },
  })
}

export const useCreateRecord = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: any) => api.post('/api/compliance/records', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['compliance', 'records'] }),
  })
}

export const useUpdateRecord = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: string; data: any }) =>
      api.put(`/api/compliance/records/${vars.id}`, vars.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['compliance', 'records'] }),
  })
}

export const useComplianceSummary = () => {
  return useQuery({
    queryKey: ['compliance', 'summary'],
    queryFn: async () => {
      const resp = await api.get('/api/compliance/summary')
      return resp.data as StatusCount[]
    },
  })
}
