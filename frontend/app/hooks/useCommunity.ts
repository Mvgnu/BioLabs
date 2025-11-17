'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import type {
  CommunityPortfolio,
  CommunityPortfolioAsset,
  CommunityPortfolioEngagement,
  CommunityFeedEntry,
  CommunityTrending,
  CommunityModerationEvent,
} from '../types'

type PortfolioFilters = {
  visibility?: 'public' | 'restricted'
  includeUnpublished?: boolean
}

export const useCommunityPortfolios = (filters: PortfolioFilters = {}) =>
  useQuery({
    queryKey: ['community', 'portfolios', filters],
    queryFn: async () => {
      const res = await api.get('/api/community/portfolios', {
        params: {
          visibility: filters.visibility ?? 'public',
          include_unpublished: filters.includeUnpublished ?? false,
        },
      })
      return res.data as CommunityPortfolio[]
    },
  })

export const useCommunityFeed = (limit = 10) =>
  useQuery({
    queryKey: ['community', 'feed', limit],
    queryFn: async () => {
      const res = await api.get('/api/community/feed', { params: { limit } })
      return res.data as CommunityFeedEntry[]
    },
  })

export const useTrendingPortfolios = (timeframe: '24h' | '7d' | '30d' = '7d') =>
  useQuery({
    queryKey: ['community', 'trending', timeframe],
    queryFn: async () => {
      const res = await api.get('/api/community/trending', { params: { timeframe } })
      return res.data as CommunityTrending
    },
  })

export const useCreatePortfolio = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: {
      slug: string
      title: string
      summary?: string
      tags?: string[]
      license?: string
      assets?: Array<Omit<CommunityPortfolioAsset, 'id' | 'guardrail_snapshot' | 'created_at'>>
    }) => {
      const res = await api.post('/api/community/portfolios', payload)
      return res.data as CommunityPortfolio
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['community', 'portfolios'] })
      qc.invalidateQueries({ queryKey: ['community', 'feed'] })
      qc.invalidateQueries({ queryKey: ['community', 'trending'] })
    },
  })
}

export const useAddPortfolioAsset = (portfolioId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (asset: {
      asset_type: 'protocol' | 'dna_asset' | 'planner_session'
      asset_id: string
      asset_version_id?: string
      planner_session_id?: string
      meta?: Record<string, unknown>
    }) => {
      const res = await api.post(`/api/community/portfolios/${portfolioId}/assets`, asset)
      return res.data as CommunityPortfolio
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['community', 'portfolios'] })
      qc.invalidateQueries({ queryKey: ['community', 'feed'] })
      qc.invalidateQueries({ queryKey: ['community', 'trending'] })
    },
  })
}

export const useRecordPortfolioEngagement = (portfolioId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: { interaction: 'view' | 'star' | 'bookmark' | 'review'; weight?: number }) => {
      const res = await api.post(`/api/community/portfolios/${portfolioId}/engagements`, payload)
      return res.data as CommunityPortfolioEngagement
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['community', 'feed'] })
      qc.invalidateQueries({ queryKey: ['community', 'trending'] })
    },
  })
}

export const useModeratePortfolio = (portfolioId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: { outcome: 'cleared' | 'requires_mitigation' | 'blocked'; notes?: string }) => {
      const res = await api.post(`/api/community/portfolios/${portfolioId}/moderation`, payload)
      return res.data as CommunityModerationEvent
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['community', 'portfolios'] })
      qc.invalidateQueries({ queryKey: ['community', 'feed'] })
      qc.invalidateQueries({ queryKey: ['community', 'trending'] })
    },
  })
}
