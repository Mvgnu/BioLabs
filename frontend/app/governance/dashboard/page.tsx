'use client'

import React, { useMemo } from 'react'
import CustodyFreezerMap from '../../components/governance/CustodyFreezerMap'
import CustodyLedgerPanel from '../../components/governance/CustodyLedgerPanel'
import GuardrailHealthDashboard from '../../components/governance/GuardrailHealthDashboard'
import OverdueDashboard from '../../components/governance/OverdueDashboard'
import { useCustodyFreezers, useCustodyLogs } from '../../hooks/useCustodyGovernance'
import { useGovernanceAnalytics, useGuardrailHealth } from '../../hooks/useExperimentConsole'
import type { GovernanceStageMetrics } from '../../types'

// purpose: governance operator dashboard surfacing overdue ladder analytics and guardrail breaches
// inputs: governance analytics hook returning shared ladder metadata
// outputs: renders overdue dashboard with actionable escalation guidance
// status: pilot
export default function GovernanceOverdueDashboardPage() {
  const analyticsQuery = useGovernanceAnalytics(null)
  const guardrailHealthQuery = useGuardrailHealth({ limit: 25 })
  const custodyFreezersQuery = useCustodyFreezers()
  const custodyLogsQuery = useCustodyLogs({ limit: 25 })

  const summary = analyticsQuery.data?.meta.overdue_stage_summary
  const stageMetrics = useMemo<Record<string, GovernanceStageMetrics> | undefined>(() => {
    const metrics = analyticsQuery.data?.meta.approval_stage_metrics
    if (!metrics) return undefined
    return metrics
  }, [analyticsQuery.data?.meta.approval_stage_metrics])

  return (
    <div className="space-y-10">
      <GuardrailHealthDashboard
        report={guardrailHealthQuery.data}
        isLoading={guardrailHealthQuery.isLoading}
        error={guardrailHealthQuery.error as Error | null}
      />
      <OverdueDashboard
        summary={summary}
        stageMetrics={stageMetrics}
        isLoading={analyticsQuery.isLoading}
        error={analyticsQuery.error as Error | null}
      />
      <CustodyFreezerMap
        units={custodyFreezersQuery.data}
        isLoading={custodyFreezersQuery.isLoading}
        error={custodyFreezersQuery.error as Error | null}
      />
      <CustodyLedgerPanel
        logs={custodyLogsQuery.data}
        isLoading={custodyLogsQuery.isLoading}
        error={custodyLogsQuery.error as Error | null}
      />
    </div>
  )
}
