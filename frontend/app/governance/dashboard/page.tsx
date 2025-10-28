'use client'

import React, { useMemo } from 'react'
import OverdueDashboard from '../../components/governance/OverdueDashboard'
import { useGovernanceAnalytics } from '../../hooks/useExperimentConsole'
import type { GovernanceStageMetrics } from '../../types'

// purpose: governance operator dashboard surfacing overdue ladder analytics and guardrail breaches
// inputs: governance analytics hook returning shared ladder metadata
// outputs: renders overdue dashboard with actionable escalation guidance
// status: pilot
export default function GovernanceOverdueDashboardPage() {
  const analyticsQuery = useGovernanceAnalytics(null)

  const summary = analyticsQuery.data?.meta.overdue_stage_summary
  const stageMetrics = useMemo<Record<string, GovernanceStageMetrics> | undefined>(() => {
    const metrics = analyticsQuery.data?.meta.approval_stage_metrics
    if (!metrics) return undefined
    return metrics
  }, [analyticsQuery.data?.meta.approval_stage_metrics])

  return (
    <OverdueDashboard
      summary={summary}
      stageMetrics={stageMetrics}
      isLoading={analyticsQuery.isLoading}
      error={analyticsQuery.error as Error | null}
    />
  )
}
