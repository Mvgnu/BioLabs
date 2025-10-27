'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { governanceApi, type GovernanceAssignmentCreate } from '../api/governance'
import type { GovernanceTemplateDraft } from '../types'

// purpose: expose governance-focused react-query hooks for admin UI
// inputs: governance API helper methods
// outputs: cached queries and mutations for templates and assignments
// status: experimental
export const useGovernanceTemplates = (includeAll = false) => {
  return useQuery({
    queryKey: ['governance', 'templates', includeAll],
    queryFn: () => governanceApi.listTemplates({ includeAll }),
    staleTime: 2 * 60 * 1000,
  })
}

export const useGovernanceTemplate = (templateId?: string) => {
  return useQuery({
    queryKey: ['governance', 'template', templateId],
    queryFn: () => governanceApi.getTemplate(templateId!),
    enabled: Boolean(templateId),
    staleTime: 60 * 1000,
  })
}

export const useCreateGovernanceTemplate = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: GovernanceTemplateDraft) =>
      governanceApi.createTemplate(payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['governance', 'templates'] })
    },
  })
}

export const useGovernanceAssignments = (templateId?: string) => {
  return useQuery({
    queryKey: ['governance', 'assignments', templateId],
    queryFn: () => governanceApi.listAssignments(templateId!),
    enabled: Boolean(templateId),
    staleTime: 60 * 1000,
  })
}

export const useCreateGovernanceAssignment = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: GovernanceAssignmentCreate) =>
      governanceApi.createAssignment(payload),
    onSuccess: (assignment) => {
      qc.invalidateQueries({
        queryKey: ['governance', 'assignments', assignment.template_id],
      })
    },
  })
}

export const useDeleteGovernanceAssignment = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { assignmentId: string; templateId: string }) =>
      governanceApi.deleteAssignment(vars.assignmentId),
    onSuccess: (assignmentId, vars) => {
      qc.invalidateQueries({ queryKey: ['governance', 'templates'] })
      qc.invalidateQueries({ queryKey: ['governance', 'assignments', vars.templateId] })
    },
  })
}
