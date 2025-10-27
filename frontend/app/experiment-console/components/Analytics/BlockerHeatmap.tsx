import React, { useMemo } from 'react'

import type { GovernanceAnalyticsPreviewSummary } from '../../../types'

interface BlockerHeatmapProps {
  items: GovernanceAnalyticsPreviewSummary[]
}

// purpose: surface stage indexes with recurrent blockers across previews
// status: pilot

export default function BlockerHeatmap({ items }: BlockerHeatmapProps) {
  const stageCounts = useMemo(() => {
    const counts = new Map<number, number>()
    items.forEach((item) => {
      item.blocker_heatmap.forEach((stageIndex) => {
        counts.set(stageIndex, (counts.get(stageIndex) ?? 0) + 1)
      })
    })
    return counts
  }, [items])

  if (stageCounts.size === 0) {
    return (
      <p className="text-sm text-neutral-500" data-testid="blocker-heatmap-empty">
        No blockers detected across recent previews.
      </p>
    )
  }

  const maxCount = Math.max(...stageCounts.values()) || 1

  return (
    <div className="space-y-3" data-testid="blocker-heatmap">
      {[...stageCounts.entries()].map(([stage, count]) => {
        const intensity = count / maxCount
        return (
          <div key={stage} className="flex items-center gap-3">
            <span className="text-sm font-medium text-neutral-700">Stage {stage}</span>
            <div className="flex-1 h-2 rounded-full bg-neutral-100 overflow-hidden">
              <div
                className="h-full bg-amber-500"
                style={{ width: `${Math.round(intensity * 100)}%` }}
              />
            </div>
            <span className="text-xs text-neutral-500">{count} blocker{count === 1 ? '' : 's'}</span>
          </div>
        )
      })}
    </div>
  )
}
