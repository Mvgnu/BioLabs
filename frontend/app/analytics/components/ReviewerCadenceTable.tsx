'use client'

import clsx from 'clsx'
import React from 'react'

import type {
  GovernanceAnalyticsLatencyBand,
  GovernanceReviewerCadenceSummary,
  ReviewerLoadBand,
} from '../../types'

// purpose: reusable table primitive for reviewer cadence analytics across dashboards
// inputs: reviewer cadence summaries with latency histograms and churn metrics
// outputs: stateless table markup suitable for composition inside cards or panels
// status: pilot

export interface ReviewerCadenceTableProps {
  reviewers: GovernanceReviewerCadenceSummary[]
  density?: 'comfortable' | 'compact'
  className?: string
}

const loadBandCopy: Record<ReviewerLoadBand, string> = {
  light: 'Light load',
  steady: 'Steady load',
  saturated: 'Saturated',
}

const loadBandTone: Record<ReviewerLoadBand, string> = {
  light: 'bg-emerald-50 text-emerald-700 border border-emerald-100',
  steady: 'bg-amber-50 text-amber-700 border border-amber-100',
  saturated: 'bg-rose-50 text-rose-700 border border-rose-100',
}

const formatNumber = (
  value: number | null | undefined,
  options?: Intl.NumberFormatOptions,
) => {
  if (value === null || value === undefined) {
    return '—'
  }
  return new Intl.NumberFormat(undefined, options).format(value)
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

const LatencyBands = ({
  bands,
}: {
  bands: GovernanceAnalyticsLatencyBand[]
}) => (
  <div className="flex flex-wrap gap-2 text-xs text-neutral-500">
    {bands.map((band) => (
      <span key={band.label} className="flex items-center gap-1">
        <span className="font-medium text-neutral-700">{latencyLabel(band)}</span>
        <span>{formatNumber(band.count)}</span>
      </span>
    ))}
  </div>
)

const cadenceClassName = (band: ReviewerLoadBand) =>
  clsx(
    'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
    loadBandTone[band],
  )

const reviewerLabel = (reviewer: GovernanceReviewerCadenceSummary) => {
  if (reviewer.reviewer_name) {
    return reviewer.reviewer_name
  }
  if (reviewer.reviewer_email) {
    return reviewer.reviewer_email
  }
  return reviewer.reviewer_id.slice(0, 8)
}

export function ReviewerCadenceTable({
  reviewers,
  density = 'comfortable',
  className,
}: ReviewerCadenceTableProps) {
  const rowPadding = density === 'compact' ? 'px-2 py-2' : 'px-3 py-3'

  if (reviewers.length === 0) {
    return (
      <div className={clsx('text-sm text-neutral-500', className)}>
        No reviewer cadence telemetry available yet.
      </div>
    )
  }

  return (
    <div className={clsx('overflow-x-auto', className)} data-testid="reviewer-cadence-table">
      <table className="min-w-full divide-y divide-neutral-200 text-sm">
        <thead className="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
          <tr>
            <th scope="col" className="px-3 py-2 text-left font-medium">
              Reviewer
            </th>
            <th scope="col" className="px-3 py-2 text-left font-medium">
              Load band
            </th>
            <th scope="col" className="px-3 py-2 text-left font-medium">
              Completed
            </th>
            <th scope="col" className="px-3 py-2 text-left font-medium">
              Pending
            </th>
            <th scope="col" className="px-3 py-2 text-left font-medium">
              Avg latency
            </th>
            <th scope="col" className="px-3 py-2 text-left font-medium">
              P50 latency
            </th>
            <th scope="col" className="px-3 py-2 text-left font-medium">
              P90 latency
            </th>
            <th scope="col" className="px-3 py-2 text-left font-medium">
              Blocker trend
            </th>
            <th scope="col" className="px-3 py-2 text-left font-medium">
              Churn signal
            </th>
            <th scope="col" className="px-3 py-2 text-left font-medium">
              Publish streak
            </th>
            <th scope="col" className="px-3 py-2 text-left font-medium">
              Latency bands
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-100">
          {reviewers.map((reviewer) => (
            <tr key={reviewer.reviewer_id} className="align-top">
              <td className={rowPadding}>
                <div className="flex flex-col gap-1">
                  <span className="font-semibold text-neutral-800">
                    {reviewerLabel(reviewer)}
                  </span>
                  <span className="text-xs text-neutral-500">
                    {formatNumber(reviewer.assignment_count)} assignments
                  </span>
                </div>
              </td>
              <td className={rowPadding}>
                <span className={cadenceClassName(reviewer.load_band)}>
                  {loadBandCopy[reviewer.load_band]}
                </span>
              </td>
              <td className={rowPadding}>{formatNumber(reviewer.completion_count)}</td>
              <td className={rowPadding}>{formatNumber(reviewer.pending_count)}</td>
              <td className={rowPadding}>
                {formatDurationMinutes(reviewer.average_latency_minutes)}
              </td>
              <td className={rowPadding}>
                {formatDurationMinutes(reviewer.latency_p50_minutes)}
              </td>
              <td className={rowPadding}>
                {formatDurationMinutes(reviewer.latency_p90_minutes)}
              </td>
              <td className={rowPadding}>{formatPercent(reviewer.blocked_ratio_trailing)}</td>
              <td className={rowPadding}>
                {formatNumber(reviewer.churn_signal, { maximumFractionDigits: 1 })}
              </td>
              <td className={rowPadding}>
                <div className="flex flex-col gap-1">
                  <span
                    className={clsx(
                      'text-sm font-semibold',
                      reviewer.streak_alert ? 'text-rose-600' : 'text-neutral-700',
                    )}
                  >
                    {reviewer.publish_streak} run
                    {reviewer.publish_streak === 1 ? '' : 's'}
                  </span>
                  <span className="text-xs text-neutral-500">
                    Last publish {formatDateTime(reviewer.last_publish_at)}
                  </span>
                </div>
              </td>
              <td className={rowPadding}>
                <LatencyBands bands={reviewer.latency_bands} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
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

export default ReviewerCadenceTable
