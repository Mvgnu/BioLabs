'use client'

import React from 'react'

import { ReviewerCadenceTable } from '../../../analytics/components'
import { Card, CardBody, CardHeader } from '../../../components/ui/Card'
import type { GovernanceReviewerCadenceSummary } from '../../../types'

interface ReviewerLoadHeatmapProps {
  reviewers: GovernanceReviewerCadenceSummary[]
}

// purpose: render reviewer cadence table inside experiment console analytics layout
// inputs: reviewer cadence summaries normalised by governance analytics API
// outputs: card-wrapped table referencing shared reviewer cadence primitive
// status: pilot

export default function ReviewerLoadHeatmap({ reviewers }: ReviewerLoadHeatmapProps) {
  return (
    <Card className="md:col-span-3" data-testid="reviewer-load-heatmap">
      <CardHeader>
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-neutral-800">Reviewer Throughput</h2>
          <span className="text-xs text-neutral-500">Load, latency, and churn cadence</span>
        </div>
      </CardHeader>
      <CardBody>
        <ReviewerCadenceTable reviewers={reviewers} />
      </CardBody>
    </Card>
  )
}
