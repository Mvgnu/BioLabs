'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import type { KnowledgeArticle } from '../types'

export const useKnowledge = (tag?: string) =>
  useQuery({
    queryKey: ['knowledge', tag],
    queryFn: async () => {
      const res = await api.get('/api/knowledge/articles', { params: { tag } })
      return res.data as KnowledgeArticle[]
    },
  })

export const useCreateArticle = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: Partial<KnowledgeArticle>) => {
      const res = await api.post('/api/knowledge/articles', data)
      return res.data as KnowledgeArticle
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['knowledge'] }),
  })
}

export const useUpdateArticle = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<KnowledgeArticle> }) => {
      const res = await api.put(`/api/knowledge/articles/${id}`, data)
      return res.data as KnowledgeArticle
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['knowledge'] }),
  })
}

export const useDeleteArticle = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/api/knowledge/articles/${id}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['knowledge'] }),
  })
}
