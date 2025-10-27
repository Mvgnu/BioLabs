'use client'

import clsx from 'clsx'
import React from 'react'

import { Card, CardBody, CardHeader } from '../../../components/ui/Card'
import type {
  GovernanceAnalyticsLatencyBand,
  GovernanceAnalyticsReviewerLoad,
} from '../../../types'

interface ReviewerLoadHeatmapProps {
  reviewers: GovernanceAnalyticsReviewerLoad[]
}

// purpose: visualise reviewer throughput and blocker-churn relationships for governance dashboards
// inputs: reviewer-centric analytics payload enriched with latency bands and churn indices
// outputs: heatmap-like table emphasising reviewer load, latency distribution, and streak status cues
// status: pilot

const formatNumber = (value: number | null | undefined, options?: Intl.NumberFormatOptions) => {
  if (value === null || value === undefined) {
    return '—'
  }
  return new Intl.NumberFormat(undefined, options).format(value)
}

const latencyLabel = (band: GovernanceAnalyticsLatencyBand) => {
  switch (band.label) {
    case 'under_2h':
      return '<2h'
    case 'two_to_eight_h':
      return '2-8h'
    case 'eight_to_day':
      return '8-24h'
    case 'over_day':
      return '>24h'
    default:
      return band.label
  }
}

const severityClass = (blockedRatio?: number | null, churn?: number | null) => {
  const ratio = blockedRatio ?? 0
  const churnScore = churn ?? 0
  if (ratio >= 0.5 || churnScore >= 6) {
    return 'bg-rose-50 text-rose-700'
  }
  if (ratio >= 0.25 || churnScore >= 3) {
    return 'bg-amber-50 text-amber-700'
  }
  return 'bg-emerald-50 text-emerald-700'
}

const formatPercent = (value: number | null | undefined) => {
  if (value === null || value === undefined) {
    return '—'
  }
  return `${formatNumber(value * 100, { maximumFractionDigits: 1 })}%`
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

const renderLatencyBands = (bands: GovernanceAnalyticsLatencyBand[]) => {
  return (
    <div className="flex gap-2 text-xs text-neutral-500" data-testid="reviewer-latency-bands">
      {bands.map((band) => (
        <span key={band.label} className="flex items-center gap-1">
          <span className="font-medium text-neutral-700">{latencyLabel(band)}</span>
          <span>{formatNumber(band.count)}</span>
        </span>
      ))}
    </div>
  )
}

const reviewerName = (reviewer: GovernanceAnalyticsReviewerLoad) => {
  if (reviewer.reviewer_name) {
    return reviewer.reviewer_name
  }
  if (reviewer.reviewer_email) {
    return reviewer.reviewer_email
  }
  return reviewer.reviewer_id.slice(0, 8)
}

const formatDateTime = (value?: string | null) => {
  if (!value) {
    return '—'
  }
  try {
    return new Date(value).toLocaleString()
  } catch (error) {
    return value
  }
}

export default function ReviewerLoadHeatmap({ reviewers }: ReviewerLoadHeatmapProps) {
  return (
    <Card className="md:col-span-3" data-testid="reviewer-load-heatmap">
      <CardHeader>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-neutral-800">Reviewer Throughput</h2>
          <span className="text-xs text-neutral-500">Load vs churn &amp; blocker intensity</span>
        </div>
      </CardHeader>
      <CardBody>
        {reviewers.length === 0 ? (
          <p className="text-sm text-neutral-500">No reviewer telemetry captured for these previews yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-neutral-200 text-sm" data-testid="reviewer-load-table">
              <thead className="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
                <tr>
                  <th scope="col" className="px-3 py-2 text-left font-medium">Reviewer</th>
                  <th scope="col" className="px-3 py-2 text-left font-medium">Completed</th>
                  <th scope="col" className="px-3 py-2 text-left font-medium">Pending</th>
                  <th scope="col" className="px-3 py-2 text-left font-medium">Avg Latency</th>
                  <th scope="col" className="px-3 py-2 text-left font-medium">Blocker Trend</th>
                  <th scope="col" className="px-3 py-2 text-left font-medium">Baseline Churn</th>
                  <th scope="col" className="px-3 py-2 text-left font-medium">Rollback Precursors</th>
                  <th scope="col" className="px-3 py-2 text-left font-medium">Publish Streak</th>
                  <th scope="col" className="px-3 py-2 text-left font-medium">Latency Bands</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-100">
                {reviewers.map((reviewer) => {
                  const badgeClass = severityClass(
                    reviewer.recent_blocked_ratio,
                    reviewer.baseline_churn,
                  )
                  return (
                    <tr key={reviewer.reviewer_id} className="align-top">
                      <td className="px-3 py-3">
                        <div className="flex flex-col gap-1">
                          <span className="font-semibold text-neutral-800">{reviewerName(reviewer)}</span>
                          <span
                            className={clsx(
                              'inline-flex w-min whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium',
                              badgeClass,
                            )}
                          >
                            {formatPercent(reviewer.recent_blocked_ratio)} · {formatNumber(reviewer.baseline_churn, { maximumFractionDigits: 1 })} churn
                          </span>
                        </div>
                      </td>
                      <td className="px-3 py-3 text-neutral-700">{formatNumber(reviewer.completed_count)}</td>
                      <td className="px-3 py-3 text-neutral-700">{formatNumber(reviewer.pending_count)}</td>
                      <td className="px-3 py-3 text-neutral-700">{formatDurationMinutes(reviewer.average_latency_minutes ?? null)}</td>
                      <td className="px-3 py-3 text-neutral-700">{formatPercent(reviewer.recent_blocked_ratio)}</td>
                      <td className="px-3 py-3 text-neutral-700">{formatNumber(reviewer.baseline_churn, { maximumFractionDigits: 1 })}</td>
                      <td className="px-3 py-3 text-neutral-700">{formatNumber(reviewer.rollback_precursor_count)}</td>
                      <td className="px-3 py-3 text-neutral-700">
                        <div className="flex flex-col gap-1">
                          <span className={clsx('text-sm font-semibold', reviewer.streak_alert ? 'text-rose-600' : 'text-neutral-700')}>
                            {reviewer.current_publish_streak} run{reviewer.current_publish_streak === 1 ? '' : 's'}
                          </span>
                          <span className="text-xs text-neutral-500">Last publish {formatDateTime(reviewer.last_publish_at)}</span>
                        </div>
                      </td>
                      <td className="px-3 py-3">{renderLatencyBands(reviewer.latency_bands)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </CardBody>
    </Card>
  )
}
