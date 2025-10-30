'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import type {
  MarketplaceCreditLedgerEntry,
  MarketplaceInvoice,
  MarketplaceListing,
  MarketplacePricingPlan,
  MarketplaceRequest,
  MarketplaceSubscription,
  MarketplaceUsageEvent,
} from '../types'

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

export const useMarketplacePlans = () =>
  useQuery({
    queryKey: ['billing-plans'],
    queryFn: async () => {
      const res = await api.get('/api/billing/plans')
      return res.data as MarketplacePricingPlan[]
    },
  })

export const useCreateSubscription = (organizationId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: any) =>
      api.post(`/api/billing/organizations/${organizationId}/subscriptions`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['billing-subscriptions', organizationId] })
      qc.invalidateQueries({ queryKey: ['billing-usage', organizationId] })
    },
  })
}

export const useOrganizationUsage = (organizationId: string) =>
  useQuery({
    queryKey: ['billing-usage', organizationId],
    queryFn: async () => {
      const res = await api.get(`/api/billing/organizations/${organizationId}/usage`)
      return res.data as MarketplaceUsageEvent[]
    },
    enabled: !!organizationId,
  })

export const useOrganizationSubscription = (organizationId: string) =>
  useQuery({
    queryKey: ['billing-subscriptions', organizationId],
    queryFn: async () => {
      const plans = await api.get('/api/billing/plans')
      const res = await api.get(
        `/api/billing/organizations/${organizationId}/subscriptions`,
      )
      const subscription = res.data as MarketplaceSubscription | null
      if (!subscription) {
        return null
      }
      const plan = (plans.data as MarketplacePricingPlan[]).find(
        (candidate) => candidate.id === subscription.plan.id,
      )
      return {
        ...subscription,
        plan: plan ?? subscription.plan,
      } as MarketplaceSubscription
    },
    enabled: !!organizationId,
  })

export const useSubscriptionInvoices = (subscriptionId: string) =>
  useQuery({
    queryKey: ['billing-invoices', subscriptionId],
    queryFn: async () => {
      const res = await api.get(
        `/api/billing/subscriptions/${subscriptionId}/invoices`,
      )
      return res.data as MarketplaceInvoice[]
    },
    enabled: !!subscriptionId,
  })

export const useCreateInvoiceDraft = (subscriptionId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: { period_start: string; period_end: string }) =>
      api.post(
        `/api/billing/subscriptions/${subscriptionId}/invoices/draft`,
        payload,
      ),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['billing-invoices', subscriptionId] }),
  })
}

export const useAdjustCredits = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload: any) => api.post('/api/billing/credits/adjust', payload),
    onSuccess: (_res, vars) => {
      const subscriptionId = vars.subscription_id as string
      qc.invalidateQueries({ queryKey: ['billing-invoices', subscriptionId] })
      qc.invalidateQueries({ queryKey: ['billing-ledger', subscriptionId] })
    },
  })
}

export const useCreditLedger = (subscriptionId: string) =>
  useQuery({
    queryKey: ['billing-ledger', subscriptionId],
    queryFn: async () => {
      const res = await api.get(`/api/billing/subscriptions/${subscriptionId}/ledger`)
      return res.data as MarketplaceCreditLedgerEntry[]
    },
    enabled: !!subscriptionId,
  })
