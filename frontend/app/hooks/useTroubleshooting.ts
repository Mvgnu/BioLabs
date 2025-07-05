'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import type { TroubleshootingArticle } from '../types'

export const useArticles = (category?: string) => {
  return useQuery({
    queryKey: ['articles', category],
    queryFn: async () => {
      const resp = await api.get('/api/troubleshooting/articles', {
        params: category ? { category } : undefined,
      })
      return resp.data as TroubleshootingArticle[]
    },
  })
}

export const useCreateArticle = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: any) => api.post('/api/troubleshooting/articles', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['articles'] }),
  })
}

export const useUpdateArticle = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: string; data: any }) =>
      api.put(`/api/troubleshooting/articles/${vars.id}`, vars.data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['articles'] }),
  })
}

export const useMarkSuccess = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      api.post(`/api/troubleshooting/articles/${id}/success`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['articles'] }),
  })
}
