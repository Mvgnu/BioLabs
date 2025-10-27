'use client'

import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'

import { governanceApi } from '../../api/governance'
import type {
  GovernanceOverrideAction,
  GovernanceOverrideRecommendation,
  GovernanceOverrideRecommendationReport,
  GovernanceOverridePriority,
} from '../../types'

// purpose: expose governance override recommendations with derived groupings for experiment console
// inputs: execution id scope, query limit, governance API client
// outputs: react-query result augmented with grouped recommendations and priority buckets
// status: pilot

export interface UseGovernanceRecommendationsOptions {
  executionId?: string | null
  limit?: number | null
}

export interface RecommendationPriorityBuckets {
  high: number
  medium: number
  low: number
}

export type RecommendationGroups = Record<
  GovernanceOverrideAction,
  GovernanceOverrideRecommendation[]
>

const recommendationKey = (
  executionId: string | null,
  limit: number | null,
) => ['governance', 'override-recommendations', executionId ?? 'all', limit ?? 'default']

const emptyReport: GovernanceOverrideRecommendationReport = {
  generated_at: new Date(0).toISOString(),
  recommendations: [],
}

const initialGroups: RecommendationGroups = {
  reassign: [],
  cooldown: [],
  escalate: [],
}

const emptyBuckets: RecommendationPriorityBuckets = {
  high: 0,
  medium: 0,
  low: 0,
}

export const useGovernanceRecommendations = (
  options?: UseGovernanceRecommendationsOptions,
) => {
  const executionId = options?.executionId ?? null
  const limit = options?.limit ?? null

  const query = useQuery<GovernanceOverrideRecommendationReport>({
    queryKey: recommendationKey(executionId, limit),
    queryFn: async () => {
      const response = await governanceApi.getOverrideRecommendations({
        execution_id: executionId ?? undefined,
        limit: limit ?? undefined,
      })
      return response
    },
    staleTime: 60_000,
  })

  const report = query.data ?? emptyReport
  const recommendations = report.recommendations

  const groupedByAction = useMemo(() => {
    return recommendations.reduce<RecommendationGroups>((acc, recommendation) => {
      const action = recommendation.action
      acc[action] = acc[action] ? [...acc[action], recommendation] : [recommendation]
      return acc
    }, { ...initialGroups })
  }, [recommendations])

  const priorityBuckets = useMemo(() => {
    return recommendations.reduce<RecommendationPriorityBuckets>((acc, recommendation) => {
      acc[recommendation.priority as GovernanceOverridePriority] += 1
      return acc
    }, { ...emptyBuckets })
  }, [recommendations])

  const hasRecommendations = recommendations.length > 0
  const generatedAt = report.generated_at

  return {
    ...query,
    report,
    recommendations,
    groupedByAction,
    priorityBuckets,
    generatedAt,
    hasRecommendations,
  }
}

export type UseGovernanceRecommendationsResult = ReturnType<
  typeof useGovernanceRecommendations
>
