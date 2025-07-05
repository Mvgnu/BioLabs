'use client'
import { useQuery } from '@tanstack/react-query'
import api from '../api/client'
import type { InventoryItem } from '../types'

export const useSearchItems = (query: string) => {
  return useQuery({
    queryKey: ['search', query],
    queryFn: async () => {
      const resp = await api.get('/api/search/items', { params: { q: query } })
      return resp.data as InventoryItem[]
    },
    enabled: !!query,
  })
}

