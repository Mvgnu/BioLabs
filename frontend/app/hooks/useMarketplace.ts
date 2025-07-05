'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import type { MarketplaceListing, MarketplaceRequest } from '../types'

export const useMarketplaceListings = () =>
  useQuery({
    queryKey: ['marketplace-listings'],
    queryFn: async () => {
      const res = await api.get('/api/marketplace/listings')
      return res.data as MarketplaceListing[]
    },
  })

export const useCreateListing = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: any) => api.post('/api/marketplace/listings', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['marketplace-listings'] }),
  })
}

export const useCreateRequest = (listingId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: any) =>
      api.post(`/api/marketplace/listings/${listingId}/requests`, data),
    onSuccess: () => qc.invalidateQueries({
      queryKey: ['marketplace-requests', listingId],
    }),
  })
}

export const useMarketplaceRequests = (listingId: string) =>
  useQuery({
    queryKey: ['marketplace-requests', listingId],
    queryFn: async () => {
      const res = await api.get(
        `/api/marketplace/listings/${listingId}/requests`
      )
      return res.data as MarketplaceRequest[]
    },
    enabled: !!listingId,
  })

export const useAcceptRequest = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      api.post(`/api/marketplace/requests/${id}/accept`),
    onSuccess: (_res, vars) =>
      qc.invalidateQueries({ queryKey: ['marketplace-requests', vars] }),
  })
}

export const useRejectRequest = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) =>
      api.post(`/api/marketplace/requests/${id}/reject`),
    onSuccess: (_res, vars) =>
      qc.invalidateQueries({ queryKey: ['marketplace-requests', vars] }),
  })
}
