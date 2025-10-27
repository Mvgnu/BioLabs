'use client'

import React from 'react'

import { Card, CardBody, CardHeader } from '../../../components/ui/Card'
import { useGovernanceAnalytics } from '../../../hooks/useExperimentConsole'
import type { GovernanceAnalyticsReport } from '../../../types'
import BlockerHeatmap from './BlockerHeatmap'
import LadderLoadChart from './LadderLoadChart'
import SlaAccuracyChart from './SlaAccuracyChart'

interface GovernanceAnalyticsPanelProps {
  executionId?: string | null
}

// purpose: orchestrate governance analytics visualisations for the experiment console
// status: pilot

const renderEmptyState = (label: string) => (
  <div className="text-sm text-neutral-500" data-testid="governance-analytics-empty">
    {label}
  </div>
)

export default function GovernanceAnalyticsPanel({ executionId }: GovernanceAnalyticsPanelProps) {
  const query = useGovernanceAnalytics(executionId ?? null)

  if (query.isLoading) {
    return (
      <section
        className="border border-neutral-200 rounded-lg bg-white shadow-sm p-6"
        data-testid="governance-analytics-loading"
      >
        <p className="text-sm text-neutral-600">Loading governance analytics…</p>
      </section>
    )
  }

  if (query.isError) {
    return (
      <section
        className="border border-rose-200 rounded-lg bg-rose-50 shadow-sm p-6"
        data-testid="governance-analytics-error"
      >
        <p className="text-sm text-rose-600">
          Unable to retrieve governance analytics for this execution.
        </p>
      </section>
    )
  }

  const analytics = query.data as GovernanceAnalyticsReport | undefined
  if (!analytics) {
    return renderEmptyState('No governance analytics available yet. Run a preview to populate this view.')
  }

  if (!analytics.results.length) {
    return renderEmptyState('Governance previews have not produced analytics summaries for this execution.')
  }

  return (
    <section className="grid gap-4 md:grid-cols-3" data-testid="governance-analytics-panel">
      <Card className="md:col-span-2">
        <CardHeader>
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-neutral-800">SLA Accuracy</h2>
            <span className="text-xs text-neutral-500">Preview vs execution outcomes</span>
          </div>
        </CardHeader>
        <CardBody>
          <SlaAccuracyChart totals={analytics.totals} items={analytics.results} />
        </CardBody>
      </Card>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-neutral-800">Blocker Heatmap</h2>
            <span className="text-xs text-neutral-500">Stages with recurring blockers</span>
          </div>
        </CardHeader>
        <CardBody>
          <BlockerHeatmap items={analytics.results} />
        </CardBody>
      </Card>
      <Card className="md:col-span-3">
        <CardHeader>
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-neutral-800">Ladder Load &amp; Risk</h2>
            <span className="text-xs text-neutral-500">Overrides and blocked ratios per preview</span>
          </div>
        </CardHeader>
        <CardBody>
          <LadderLoadChart items={analytics.results} />
        </CardBody>
      </Card>
    </section>
  )
}
