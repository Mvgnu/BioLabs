'use client'

import React from 'react'

import { Card, CardBody, CardHeader } from '../../../components/ui/Card'
import type { GovernanceAnalyticsReviewerLoad } from '../../../types'

interface ReviewerStreakAlertsProps {
  reviewers: GovernanceAnalyticsReviewerLoad[]
  totalAlerts: number
}

// purpose: surface reviewer publish cadence streaks that warrant proactive staffing or override action
// inputs: reviewer load analytics annotated with streak_alert flags
// outputs: alert list summarising cadence status and recent publish timing for decision makers
// status: pilot

const reviewerLabel = (reviewer: GovernanceAnalyticsReviewerLoad) => {
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

export default function ReviewerStreakAlerts({
  reviewers,
  totalAlerts,
}: ReviewerStreakAlertsProps) {
  const alertingReviewers = reviewers
    .filter((reviewer) => reviewer.streak_alert)
    .sort((a, b) => b.current_publish_streak - a.current_publish_streak)

  return (
    <Card data-testid="reviewer-streak-alerts">
      <CardHeader>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-neutral-800">Publish Streak Alerts</h2>
          <span className="text-xs text-neutral-500">{totalAlerts} active</span>
        </div>
      </CardHeader>
      <CardBody className="space-y-4">
        {alertingReviewers.length === 0 ? (
          <p className="text-sm text-neutral-500">
            No sustained publish streaks detected. Review cadence is within guardrails.
          </p>
        ) : (
          <ul className="space-y-3">
            {alertingReviewers.map((reviewer) => (
              <li
                key={reviewer.reviewer_id}
                className="rounded-md border border-rose-100 bg-rose-50 p-3"
                data-testid="reviewer-streak-alert"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-semibold text-rose-700">
                    {reviewerLabel(reviewer)}
                  </span>
                  <span className="text-xs font-medium uppercase tracking-wide text-rose-600">
                    {reviewer.current_publish_streak} consecutive publishes
                  </span>
                </div>
                <dl className="mt-2 grid grid-cols-2 gap-2 text-xs text-rose-700">
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
        )}
      </CardBody>
    </Card>
  )
}
