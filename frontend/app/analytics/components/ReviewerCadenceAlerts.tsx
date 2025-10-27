'use client'

import React from 'react'

import type { GovernanceReviewerCadenceSummary } from '../../types'

// purpose: lightweight list primitive highlighting reviewer publish streak alerts
// inputs: reviewer cadence summaries filtered for streak alerts
// outputs: structured list ready for embedding into cards or notification panels
// status: pilot

export interface ReviewerCadenceAlertsProps {
  reviewers: GovernanceReviewerCadenceSummary[]
  className?: string
  renderEmptyState?: () => React.ReactNode
}

const reviewerLabel = (reviewer: GovernanceReviewerCadenceSummary) => {
  if (reviewer.reviewer_name) {
    return reviewer.reviewer_name
  }
  if (reviewer.reviewer_email) {
    return reviewer.reviewer_email
  }
  return reviewer.reviewer_id.slice(0, 8)
}

const formatDate = (value?: string | null) => {
  if (!value) {
    return 'Unknown'
  }
  try {
    return new Date(value).toLocaleDateString()
  } catch (error) {
    return value
  }
}

export function ReviewerCadenceAlerts({
  reviewers,
  className,
  renderEmptyState,
}: ReviewerCadenceAlertsProps) {
  const alerting = React.useMemo(
    () => reviewers.filter((reviewer) => reviewer.streak_alert),
    [reviewers],
  )

  if (alerting.length === 0) {
    return (
      <div className={className} data-testid="reviewer-cadence-alerts-empty">
        {renderEmptyState ? (
          renderEmptyState()
        ) : (
          <p className="text-sm text-neutral-500">
            No sustained publish streaks detected. Cadence is within guardrails.
          </p>
        )}
      </div>
    )
  }

  return (
    <ul className={className} data-testid="reviewer-cadence-alerts">
      {alerting.map((reviewer) => (
        <li key={reviewer.reviewer_id} className="space-y-2 rounded-md border border-rose-100 bg-rose-50 p-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-semibold text-rose-700">
              {reviewerLabel(reviewer)}
            </span>
            <span className="text-xs font-medium uppercase tracking-wide text-rose-600">
              {reviewer.publish_streak} consecutive publishes
            </span>
          </div>
          <dl className="grid grid-cols-2 gap-2 text-xs text-rose-700">
            <div>
              <dt className="uppercase tracking-wide">Last publish</dt>
              <dd>{formatDate(reviewer.last_publish_at)}</dd>
            </div>
            <div>
              <dt className="uppercase tracking-wide">Rollback precursors</dt>
              <dd>{reviewer.rollback_precursor_count}</dd>
            </div>
          </dl>
        </li>
      ))}
    </ul>
  )
}

export default ReviewerCadenceAlerts
