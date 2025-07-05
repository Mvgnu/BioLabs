'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import type { Post, Follow } from '../types'

export const useFeed = () =>
  useQuery({
    queryKey: ['feed'],
    queryFn: async () => {
      const res = await api.get('/api/community/feed')
      return res.data as Post[]
    },
  })

export const useCreatePost = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: { content: string }) => {
      const res = await api.post('/api/community/posts', data)
      return res.data as Post
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['feed'] }),
  })
}

export const useFollow = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      const res = await api.post(`/api/community/follow/${id}`)
      return res.data as Follow
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['feed'] }),
  })
}

export const useUnfollow = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/api/community/follow/${id}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['feed'] }),
  })
}
