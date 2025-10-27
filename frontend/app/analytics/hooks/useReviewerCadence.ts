'use client'

import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'

import { governanceApi } from '../../api/governance'
import type { ReviewerLoadBand } from '../../types'

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

export const useReviewerCadence = (options?: UseReviewerCadenceOptions) => {
  const executionId = options?.executionId ?? null
  const limit = options?.limit ?? 50

  const query = useQuery({
    queryKey: reviewerCadenceKey(executionId, limit),
    queryFn: async () => {
      const response = await governanceApi.getAnalytics({
        execution_id: executionId ?? undefined,
        limit,
      })
      return response.reviewer_cadence
    },
  })

  const reviewers = query.data ?? []

  const loadBandCounts = useMemo(() => {
    if (!reviewers.length) {
      return emptyCounts
    }
    return reviewers.reduce<ReviewerLoadBandCounts>((acc, reviewer) => {
      acc[reviewer.load_band as ReviewerLoadBand] += 1
      return acc
    }, { ...emptyCounts })
  }, [reviewers])

  const streakAlerts = useMemo(
    () => reviewers.filter((reviewer) => reviewer.streak_alert),
    [reviewers],
  )

  return {
    ...query,
    reviewers,
    loadBandCounts,
    streakAlerts,
  }
}

export type UseReviewerCadenceResult = ReturnType<typeof useReviewerCadence>
