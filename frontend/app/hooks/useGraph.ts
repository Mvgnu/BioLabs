'use client'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import type { GraphData } from '../types'

export const useItemGraph = (itemId: string, depth = 1) => {
  return useQuery({
    queryKey: ['graph', itemId, depth],
    queryFn: async () => {
      const resp = await api.get(`/api/inventory/items/${itemId}/graph`, {
        params: { depth }
      })
      return resp.data as GraphData
    }
  })
}
