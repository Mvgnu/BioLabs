'use client'

import clsx from 'clsx'
import React from 'react'

// purpose: compact badge summarising reviewer cadence streak alerts for dashboards
// inputs: streak alert count and optional total reviewer count for context
// outputs: color-coded badge conveying guardrail status to operators
// status: pilot

export interface ReviewerCadenceAlertBadgeProps {
  streakAlertCount: number
  reviewerCount?: number
  className?: string
}

export function ReviewerCadenceAlertBadge({
  streakAlertCount,
  reviewerCount,
  className,
}: ReviewerCadenceAlertBadgeProps) {
  const hasAlerts = streakAlertCount > 0
  const label = hasAlerts
    ? `${streakAlertCount} reviewer${streakAlertCount === 1 ? '' : 's'} on streak`
    : 'No streak alerts'

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-medium',
        hasAlerts
          ? 'bg-rose-100 text-rose-700 border border-rose-200'
          : 'bg-emerald-50 text-emerald-700 border border-emerald-100',
        className,
      )}
    >
      <span>{label}</span>
      {typeof reviewerCount === 'number' && (
        <span className="text-xs font-normal text-neutral-500">
          {reviewerCount} total
        </span>
      )}
    </span>
  )
}

export default ReviewerCadenceAlertBadge
