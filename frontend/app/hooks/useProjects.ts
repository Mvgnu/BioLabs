'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import type { Project, ProjectTask } from '../types'

export const useProjects = () => {
  return useQuery({
    queryKey: ['projects'],
    queryFn: async () => {
      const resp = await api.get('/api/projects')
      return resp.data as Project[]
    },
  })
}

export const useCreateProject = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: any) => api.post('/api/projects', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  })
}

export const useProjectTasks = (projectId: string) => {
  return useQuery({
    queryKey: ['project-tasks', projectId],
    queryFn: async () => {
      const resp = await api.get(`/api/projects/${projectId}/tasks`)
      return resp.data as ProjectTask[]
    },
  })
}

export const useCreateTask = (projectId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: any) =>
      api.post(`/api/projects/${projectId}/tasks`, data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['project-tasks', projectId] }),
  })
}

export const useUpdateTask = (projectId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: string; data: any }) =>
      api.put(`/api/projects/${projectId}/tasks/${vars.id}`, vars.data),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['project-tasks', projectId] }),
  })
}

export const useDeleteTask = (projectId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      api.delete(`/api/projects/${projectId}/tasks/${id}`),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['project-tasks', projectId] }),
  })
}
