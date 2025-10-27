'use client'

import clsx from 'clsx'
import React from 'react'

import type {
  GovernanceReviewerLoadBandCounts,
  ReviewerLoadBand,
} from '../../types'

// purpose: visualise reviewer load distribution as governance-friendly heatmap chips
// inputs: reviewer load band counts derived from governance cadence analytics
// outputs: stateless heatmap segments usable inside cards and compact dashboards
// status: pilot

export interface ReviewerLoadHeatmapProps {
  counts: GovernanceReviewerLoadBandCounts
  className?: string
  showLabels?: boolean
}

const bandOrder: ReviewerLoadBand[] = ['light', 'steady', 'saturated']

const bandLabelCopy: Record<ReviewerLoadBand, string> = {
  light: 'Light',
  steady: 'Steady',
  saturated: 'Saturated',
}

const bandClasses: Record<ReviewerLoadBand, string> = {
  light: 'bg-emerald-100 text-emerald-700',
  steady: 'bg-amber-100 text-amber-700',
  saturated: 'bg-rose-100 text-rose-700',
}

const sumCounts = (counts: GovernanceReviewerLoadBandCounts) =>
  bandOrder.reduce((acc, band) => acc + (counts[band] ?? 0), 0)

export function ReviewerLoadHeatmap({
  counts,
  className,
  showLabels = true,
}: ReviewerLoadHeatmapProps) {
  const total = sumCounts(counts)

  if (!total) {
    return (
      <div className={clsx('text-sm text-neutral-500', className)}>
        No reviewer load telemetry yet.
      </div>
    )
  }

  return (
    <div className={clsx('flex flex-col gap-2', className)}>
      <div className="flex overflow-hidden rounded-md border border-neutral-200">
        {bandOrder.map((band) => {
          const value = counts[band] ?? 0
          const width = value ? `${Math.max((value / total) * 100, 6)}%` : '0%'
          return (
            <div
              key={band}
              className={clsx(
                'flex items-center justify-center text-xs font-semibold transition-[flex-basis] duration-150 ease-out',
                bandClasses[band],
                !value && 'hidden',
              )}
              style={{ width }}
              aria-label={`${bandLabelCopy[band]} load reviewers`}
            >
              {value}
            </div>
          )
        })}
      </div>
      {showLabels && (
        <dl className="grid grid-cols-3 gap-2 text-xs text-neutral-600">
          {bandOrder.map((band) => (
            <div key={band} className="flex flex-col gap-1">
              <dt className="font-medium text-neutral-700">{bandLabelCopy[band]}</dt>
              <dd>{counts[band] ?? 0}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  )
}

export default ReviewerLoadHeatmap
