'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import type { Comment } from '../types'

export const useComments = (params?: { item_id?: string; entry_id?: string }) =>
  useQuery({
    queryKey: ['comments', params],
    queryFn: async () => {
      const res = await api.get('/api/comments', { params })
      return res.data as Comment[]
    },
  })

export const useCreateComment = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: Partial<Comment>) => {
      const res = await api.post('/api/comments/', data)
      return res.data as Comment
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['comments'] }),
  })
}

export const useUpdateComment = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<Comment> }) => {
      const res = await api.put(`/api/comments/${id}`, data)
      return res.data as Comment
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['comments'] }),
  })
}

export const useDeleteComment = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/api/comments/${id}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['comments'] }),
  })
}
