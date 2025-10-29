'use client'

import React, { useMemo } from 'react'
import CustodyEscalationPanel from '../../components/governance/CustodyEscalationPanel'
import CustodyFreezerMap from '../../components/governance/CustodyFreezerMap'
import CustodyLedgerPanel from '../../components/governance/CustodyLedgerPanel'
import GuardrailHealthDashboard from '../../components/governance/GuardrailHealthDashboard'
import OverdueDashboard from '../../components/governance/OverdueDashboard'
import {
  useAcknowledgeCustodyEscalation,
  useCustodyEscalations,
  useCustodyFreezers,
  useCustodyLogs,
  useCustodyProtocols,
  useFreezerFaults,
  useResolveCustodyEscalation,
  useTriggerCustodyEscalationNotification,
} from '../../hooks/useCustodyGovernance'
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
  const custodyEscalationsQuery = useCustodyEscalations()
  const custodyProtocolsQuery = useCustodyProtocols({ limit: 10 })
  const freezerFaultsQuery = useFreezerFaults()
  const acknowledgeEscalation = useAcknowledgeCustodyEscalation()
  const resolveEscalation = useResolveCustodyEscalation()
  const notifyEscalation = useTriggerCustodyEscalationNotification()

  const summary = analyticsQuery.data?.meta.overdue_stage_summary
  const stageMetrics = useMemo<Record<string, GovernanceStageMetrics> | undefined>(() => {
    const metrics = analyticsQuery.data?.meta.approval_stage_metrics
    if (!metrics) return undefined
    return metrics
  }, [analyticsQuery.data?.meta.approval_stage_metrics])

  const busyEscalations = useMemo(() => {
    const ids = new Set<string>()
    const ackId = acknowledgeEscalation.variables as string | undefined
    if (acknowledgeEscalation.isPending && ackId) {
      ids.add(ackId)
    }
    const resolveId = resolveEscalation.variables as string | undefined
    if (resolveEscalation.isPending && resolveId) {
      ids.add(resolveId)
    }
    const notifyId = notifyEscalation.variables as string | undefined
    if (notifyEscalation.isPending && notifyId) {
      ids.add(notifyId)
    }
    return ids
  }, [
    acknowledgeEscalation.isPending,
    acknowledgeEscalation.variables,
    resolveEscalation.isPending,
    resolveEscalation.variables,
    notifyEscalation.isPending,
    notifyEscalation.variables,
  ])

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
      <CustodyEscalationPanel
        escalations={custodyEscalationsQuery.data}
        faults={freezerFaultsQuery.data}
        isEscalationLoading={custodyEscalationsQuery.isLoading}
        isFaultLoading={freezerFaultsQuery.isLoading}
        protocols={custodyProtocolsQuery.data}
        isProtocolLoading={custodyProtocolsQuery.isLoading}
        escalationError={custodyEscalationsQuery.error as Error | null}
        faultError={freezerFaultsQuery.error as Error | null}
        protocolError={custodyProtocolsQuery.error as Error | null}
        onAcknowledge={(id) => acknowledgeEscalation.mutate(id)}
        onResolve={(id) => resolveEscalation.mutate(id)}
        onNotify={(id) => notifyEscalation.mutate(id)}
        busyIds={busyEscalations}
      />
      <CustodyLedgerPanel
        logs={custodyLogsQuery.data}
        isLoading={custodyLogsQuery.isLoading}
        error={custodyLogsQuery.error as Error | null}
      />
    </div>
  )
}
