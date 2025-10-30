'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import type {
  ComplianceOrganization,
  ComplianceRecord,
  ComplianceReportSummary,
  LegalHold,
  ResidencyPolicy,
  StatusCount,
} from '../types'

export const useComplianceOrganizations = () => {
  return useQuery({
    queryKey: ['compliance', 'organizations'],
    queryFn: async () => {
      const resp = await api.get('/api/compliance/organizations')
      return resp.data as ComplianceOrganization[]
    },
  })
}

export const useCreateOrganization = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Partial<ComplianceOrganization>) =>
      api.post('/api/compliance/organizations', payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['compliance', 'organizations'] })
      qc.invalidateQueries({ queryKey: ['compliance', 'report'] })
    },
  })
}

export const useUpdateOrganization = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (variables: { id: string; payload: Partial<ComplianceOrganization> }) =>
      api.put(`/api/compliance/organizations/${variables.id}`, variables.payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['compliance', 'organizations'] })
      qc.invalidateQueries({ queryKey: ['compliance', 'report'] })
    },
  })
}

export const useResidencyPolicies = (organizationId: string | null) => {
  return useQuery({
    queryKey: ['compliance', 'policies', organizationId],
    enabled: !!organizationId,
    queryFn: async () => {
      const resp = await api.get(`/api/compliance/organizations/${organizationId}/policies`)
      return resp.data as ResidencyPolicy[]
    },
  })
}

export const useUpsertResidencyPolicy = (organizationId: string | null) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Partial<ResidencyPolicy>) =>
      api.post(`/api/compliance/organizations/${organizationId}/policies`, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['compliance', 'policies', organizationId] })
      qc.invalidateQueries({ queryKey: ['compliance', 'report'] })
    },
  })
}

export const useLegalHolds = (organizationId: string | null) => {
  return useQuery({
    queryKey: ['compliance', 'legal-holds', organizationId],
    enabled: !!organizationId,
    queryFn: async () => {
      const resp = await api.get(`/api/compliance/organizations/${organizationId}/legal-holds`)
      return resp.data as LegalHold[]
    },
  })
}

export const useCreateLegalHold = (organizationId: string | null) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: Partial<LegalHold>) =>
      api.post(`/api/compliance/organizations/${organizationId}/legal-holds`, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['compliance', 'legal-holds', organizationId] })
    },
  })
}

export const useReleaseLegalHold = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (variables: { id: string; organizationId?: string; payload?: Partial<LegalHold> }) =>
      api.post(`/api/compliance/legal-holds/${variables.id}/release`, variables.payload),
    onSuccess: (_resp, variables) => {
      if (variables.organizationId) {
        qc.invalidateQueries({ queryKey: ['compliance', 'legal-holds', variables.organizationId] })
      }
      qc.invalidateQueries({ queryKey: ['compliance', 'report'] })
    },
  })
}

export const useComplianceReport = () => {
  return useQuery({
    queryKey: ['compliance', 'report'],
    queryFn: async () => {
      const resp = await api.get('/api/compliance/reports/export')
      return resp.data as ComplianceReportSummary
    },
  })
}

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
    mutationFn: (data: Partial<ComplianceRecord>) => api.post('/api/compliance/records', data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['compliance', 'records'] })
      qc.invalidateQueries({ queryKey: ['compliance', 'summary'] })
      qc.invalidateQueries({ queryKey: ['compliance', 'report'] })
    },
  })
}

export const useUpdateRecord = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: string; data: Partial<ComplianceRecord> }) =>
      api.put(`/api/compliance/records/${vars.id}`, vars.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['compliance', 'records'] })
      qc.invalidateQueries({ queryKey: ['compliance', 'summary'] })
      qc.invalidateQueries({ queryKey: ['compliance', 'report'] })
    },
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
