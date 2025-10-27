'use client'

import React from 'react'

import { ReviewerCadenceAlerts } from '../../../analytics/components'
import { Card, CardBody, CardHeader } from '../../../components/ui/Card'
import type { GovernanceReviewerCadenceSummary } from '../../../types'

interface ReviewerStreakAlertsProps {
  reviewers: GovernanceReviewerCadenceSummary[]
  totalAlerts: number
}

// purpose: present reviewer cadence alerts within experiment console framing
// inputs: reviewer cadence summaries and total alert count from analytics totals
// outputs: card-wrapped alert list driven by shared reviewer cadence primitive
// status: pilot

export default function ReviewerStreakAlerts({
  reviewers,
  totalAlerts,
}: ReviewerStreakAlertsProps) {
  return (
    <Card data-testid="reviewer-streak-alerts">
      <CardHeader>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-neutral-800">Publish Streak Alerts</h2>
          <span className="text-xs text-neutral-500">{totalAlerts} active</span>
        </div>
      </CardHeader>
      <CardBody className="space-y-4">
        <ReviewerCadenceAlerts
          reviewers={reviewers}
          renderEmptyState={() => (
            <p className="text-sm text-neutral-500">
              No sustained publish streaks detected. Review cadence is within guardrails.
            </p>
          )}
        />
      </CardBody>
    </Card>
  )
}
