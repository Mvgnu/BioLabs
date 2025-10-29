'use client'

// purpose: fetch DNA viewer payloads with guardrail + diff metadata
// status: experimental
// depends_on: @tanstack/react-query, frontend/app/api/client

import { useQuery } from '@tanstack/react-query'

import api from '../api/client'
import type { DNAViewerPayload } from '../types'

export const useDNAViewer = (assetId: string | null, compareVersion?: string | null) => {
  return useQuery({
    queryKey: ['dnaViewer', assetId, compareVersion ?? null],
    enabled: Boolean(assetId),
    queryFn: async () => {
      if (!assetId) throw new Error('Asset id is required for viewer payloads')
      const resp = await api.get(`/api/dna-assets/${assetId}/viewer`, {
        params: compareVersion ? { compare_version: compareVersion } : undefined,
      })
      return resp.data as DNAViewerPayload
    },
    staleTime: 60_000,
  })
}
