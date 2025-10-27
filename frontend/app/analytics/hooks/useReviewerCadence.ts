'use client'

import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'

import { governanceApi } from '../../api/governance'
import type {
  GovernanceReviewerCadenceReport,
  GovernanceReviewerCadenceTotals,
  ReviewerLoadBand,
} from '../../types'

// purpose: expose reviewer cadence analytics with derived band counts for reuse across dashboards
// inputs: optional execution filter and limit, governance analytics API client
// outputs: react-query result augmented with reviewer cadence data, band counts, and streak alerts
// status: pilot

export interface UseReviewerCadenceOptions {
  executionId?: string | null
  limit?: number
}

export interface ReviewerLoadBandCounts {
  light: number
  steady: number
  saturated: number
}

const reviewerCadenceKey = (executionId: string | null, limit: number) => [
  'governance',
  'reviewer-cadence',
  executionId ?? 'all',
  limit,
]

const emptyCounts: ReviewerLoadBandCounts = { light: 0, steady: 0, saturated: 0 }
const emptyTotals: GovernanceReviewerCadenceTotals = {
  reviewer_count: 0,
  streak_alert_count: 0,
  reviewer_latency_p50_minutes: null,
  reviewer_latency_p90_minutes: null,
  load_band_counts: { ...emptyCounts },
}

export const useReviewerCadence = (options?: UseReviewerCadenceOptions) => {
  const executionId = options?.executionId ?? null
  const limit = options?.limit ?? 50

  const query = useQuery<GovernanceReviewerCadenceReport>({
    queryKey: reviewerCadenceKey(executionId, limit),
    queryFn: async () => {
      const response = await governanceApi.getReviewerCadence({
        execution_id: executionId ?? undefined,
        limit,
      })
      return response
    },
  })

  const reviewers = query.data?.reviewers ?? []
  const totals = query.data?.totals ?? emptyTotals

  const loadBandCounts = useMemo(() => {
    if (query.data?.totals) {
      return query.data.totals.load_band_counts
    }
    if (!reviewers.length) {
      return emptyCounts
    }
    return reviewers.reduce<ReviewerLoadBandCounts>((acc, reviewer) => {
      acc[reviewer.load_band as ReviewerLoadBand] += 1
      return acc
    }, { ...emptyCounts })
  }, [query.data?.totals, reviewers])

  const streakAlerts = useMemo(
    () => reviewers.filter((reviewer) => reviewer.streak_alert),
    [reviewers],
  )

  return {
    ...query,
    reviewers,
    totals,
    loadBandCounts,
    streakAlerts,
  }
}

export type UseReviewerCadenceResult = ReturnType<typeof useReviewerCadence>
