'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import type { AssistantMessage } from '../types'

export const useAssistantHistory = () =>
  useQuery({
    queryKey: ['assistant', 'history'],
    queryFn: async () => {
      const res = await api.get('/api/assistant')
      return res.data as AssistantMessage[]
    },
  })

export const useAskAssistant = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (question: string) => {
      const res = await api.post('/api/assistant/ask', { question })
      return res.data as AssistantMessage
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['assistant', 'history'] }),
  })
}
