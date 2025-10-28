'use client'

import React from 'react'

import type { GovernanceOverrideLineageAggregates } from '../../../../../types'

export interface AnalyticsLineageWidgetProps {
  summary: GovernanceOverrideLineageAggregates
}

const formatLabel = (value: string | null | undefined, fallback: string) => {
  if (!value) return fallback
  return value
}

const computeWidth = (value: number, maxValue: number) => {
  if (!maxValue || maxValue <= 0) return 0
  return Math.max(5, Math.round((value / maxValue) * 100))
}

const renderBuckets = (
  buckets: { label: string; executed: number; reversed: number; net: number }[],
  colorClass: string,
) => {
  if (buckets.length === 0) {
    return <p className="text-xs text-neutral-500">No lineage activity captured.</p>
  }
  const maxExecuted = Math.max(...buckets.map((bucket) => bucket.executed))
  return (
    <ul className="space-y-2">
      {buckets.map((bucket) => (
        <li key={`${bucket.label}-${bucket.executed}-${bucket.reversed}`} className="space-y-1">
          <div className="flex items-center justify-between text-xs font-medium text-neutral-700">
            <span>{bucket.label}</span>
            <span className="text-neutral-500">
              {bucket.executed} exec · {bucket.reversed} rev
            </span>
          </div>
          <div className="h-2 w-full rounded-full bg-neutral-200">
            <div
              className={`${colorClass} h-2 rounded-full transition-all`}
              style={{ width: `${computeWidth(bucket.executed, maxExecuted)}%` }}
              aria-hidden
            />
          </div>
          <p className="text-[11px] text-neutral-500">Net impact: {bucket.net}</p>
        </li>
      ))}
    </ul>
  )
}

// purpose: visualise aggregated override lineage analytics alongside timeline entries
// inputs: GovernanceOverrideLineageAggregates derived from backend analytics
// outputs: stacked lineage buckets with execution/reversal deltas for UI insight
// status: pilot
const AnalyticsLineageWidget = ({ summary }: AnalyticsLineageWidgetProps) => {
  const scenarios = [...summary.scenarios]
    .sort((a, b) => (b.executed_count ?? 0) - (a.executed_count ?? 0))
    .slice(0, 5)
    .map((bucket) => ({
      label: formatLabel(bucket.scenario_name, bucket.scenario_id ?? 'Scenario lineage'),
      executed: bucket.executed_count ?? 0,
      reversed: bucket.reversed_count ?? 0,
      net: bucket.net_count ?? bucket.executed_count - bucket.reversed_count,
    }))
  const notebooks = [...summary.notebooks]
    .sort((a, b) => (b.executed_count ?? 0) - (a.executed_count ?? 0))
    .slice(0, 5)
    .map((bucket) => ({
      label: formatLabel(bucket.notebook_title, bucket.notebook_entry_id ?? 'Notebook lineage'),
      executed: bucket.executed_count ?? 0,
      reversed: bucket.reversed_count ?? 0,
      net: bucket.net_count ?? bucket.executed_count - bucket.reversed_count,
    }))

  if (scenarios.length === 0 && notebooks.length === 0) {
    return null
  }

  return (
    <div className="rounded-md border border-neutral-200 bg-white p-3" data-biolab-widget="governance-lineage-analytics">
      <h4 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
        Lineage override analytics
      </h4>
      <div className="mt-2 grid gap-4 sm:grid-cols-2">
        <div>
          <h5 className="text-xs font-semibold text-neutral-600">Scenarios</h5>
          {renderBuckets(scenarios, 'bg-emerald-400')}
        </div>
        <div>
          <h5 className="text-xs font-semibold text-neutral-600">Notebooks</h5>
          {renderBuckets(notebooks, 'bg-blue-400')}
        </div>
      </div>
    </div>
  )
}

export default AnalyticsLineageWidget
