'use client'

import React from 'react'

import { Card, CardBody, CardHeader } from '../../../components/ui/Card'
import type {
  GovernanceAnalyticsPreviewSummary,
  GovernanceAnalyticsReport,
} from '../../../types'

interface BaselineLifecycleStatsProps {
  report: GovernanceAnalyticsReport
}

// purpose: visualise baseline lifecycle cadence metrics derived from governance analytics
// inputs: governance analytics report enriched with baseline metrics
// outputs: summary statistics and spotlight list for experiment console dashboards
// status: pilot

const formatNumber = (value: number | null | undefined, options?: Intl.NumberFormatOptions) => {
  if (value === null || value === undefined) {
    return '—'
  }
  return new Intl.NumberFormat(undefined, options).format(value)
}

const formatDurationMinutes = (value: number | null | undefined) => {
  if (value === null || value === undefined) {
    return '—'
  }
  if (value >= 120) {
    const hours = value / 60
    return `${formatNumber(hours, { maximumFractionDigits: 1 })} h`
  }
  return `${formatNumber(value, { maximumFractionDigits: 0 })} min`
}

const formatDurationDays = (value: number | null | undefined) => {
  if (value === null || value === undefined) {
    return '—'
  }
  return `${formatNumber(value, { maximumFractionDigits: 1 })} d`
}

const pickTopSummaries = (items: GovernanceAnalyticsPreviewSummary[]) => {
  return items
    .slice()
    .sort((a, b) => (b.rollback_count ?? 0) - (a.rollback_count ?? 0))
    .slice(0, 4)
}

const Stat = ({ label, value }: { label: string; value: string }) => (
  <div className="flex flex-col gap-1">
    <span className="text-xs uppercase tracking-wide text-neutral-500">{label}</span>
    <span className="text-lg font-semibold text-neutral-800" data-testid={`baseline-stat-${label.toLowerCase().replace(/[^a-z]+/g, '-')}`}>
      {value}
    </span>
  </div>
)

export default function BaselineLifecycleStats({ report }: BaselineLifecycleStatsProps) {
  const { totals, results } = report
  const highlighted = pickTopSummaries(results)

  return (
    <Card className="md:col-span-3" data-testid="baseline-lifecycle-card">
      <CardHeader>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-neutral-800">Baseline Lifecycle Pulse</h2>
          <span className="text-xs text-neutral-500">Approval cadence &amp; rollback risk</span>
        </div>
      </CardHeader>
      <CardBody className="space-y-6">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Total Baselines" value={formatNumber(totals.total_baseline_versions)} />
          <Stat label="Rollbacks" value={formatNumber(totals.total_rollbacks)} />
          <Stat
            label="Avg Approval Latency"
            value={formatDurationMinutes(totals.average_approval_latency_minutes ?? null)}
          />
          <Stat
            label="Avg Publication Cadence"
            value={formatDurationDays(totals.average_publication_cadence_days ?? null)}
          />
        </div>
        <div className="space-y-3">
          <h3 className="text-sm font-semibold text-neutral-700">Lifecycle hotspots</h3>
          {highlighted.length === 0 ? (
            <p className="text-sm text-neutral-500">No baseline lifecycle activity recorded for these previews yet.</p>
          ) : (
            <ul className="grid gap-3 md:grid-cols-2">
              {highlighted.map((item) => (
                <li
                  key={`${item.execution_id}-${item.preview_event_id}`}
                  className="rounded-md border border-neutral-200 bg-neutral-50 p-3"
                >
                  <div className="flex items-center justify-between text-sm font-medium text-neutral-700">
                    <span>Execution {item.execution_id.slice(0, 8)}</span>
                    <span className="text-xs text-amber-600">{item.rollback_count} rollback{item.rollback_count === 1 ? '' : 's'}</span>
                  </div>
                  <dl className="mt-2 grid grid-cols-2 gap-2 text-xs text-neutral-600">
                    <div>
                      <dt className="uppercase tracking-wide">Baselines</dt>
                      <dd>{formatNumber(item.baseline_version_count)}</dd>
                    </div>
                    <div>
                      <dt className="uppercase tracking-wide">Approval</dt>
                      <dd>{formatDurationMinutes(item.approval_latency_minutes ?? null)}</dd>
                    </div>
                    <div>
                      <dt className="uppercase tracking-wide">Cadence</dt>
                      <dd>{formatDurationDays(item.publication_cadence_days ?? null)}</dd>
                    </div>
                    <div>
                      <dt className="uppercase tracking-wide">Blocked Ratio</dt>
                      <dd>{formatNumber(item.blocked_ratio, { style: 'percent', maximumFractionDigits: 1 })}</dd>
                    </div>
                  </dl>
                </li>
              ))}
            </ul>
          )}
        </div>
      </CardBody>
    </Card>
  )
}
