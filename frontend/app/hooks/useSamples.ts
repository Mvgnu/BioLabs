'use client'

import { useQuery } from '@tanstack/react-query'

import api from '../api/client'
import type { InventorySampleSummary, SampleDetail } from '../types'

// purpose: expose sample custody summary/detail queries for dashboards
// status: pilot

const SAMPLE_LIST_KEY = ['samples', 'summary'] as const

export const useSampleSummaries = () => {
  return useQuery({
    queryKey: SAMPLE_LIST_KEY,
    queryFn: async () => {
      const resp = await api.get('/api/inventory/samples')
      return resp.data as InventorySampleSummary[]
    },
  })
}

export const useSampleDetail = (sampleId: string | null) => {
  return useQuery({
    queryKey: ['samples', 'detail', sampleId],
    queryFn: async () => {
      if (!sampleId) {
        return null as SampleDetail | null
      }
      const resp = await api.get(`/api/inventory/items/${sampleId}/custody`)
      return resp.data as SampleDetail
    },
    enabled: Boolean(sampleId),
  })
}
