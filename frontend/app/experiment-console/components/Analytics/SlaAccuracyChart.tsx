import React, { useMemo } from 'react'

import type {
  GovernanceAnalyticsPreviewSummary,
  GovernanceAnalyticsTotals,
} from '../../../types'

interface SlaAccuracyChartProps {
  totals: GovernanceAnalyticsTotals
  items: GovernanceAnalyticsPreviewSummary[]
}

// purpose: visualise SLA adherence ratios across governance previews
// status: pilot

const formatPercent = (value: number) => `${Math.round(value * 100)}%`

export default function SlaAccuracyChart({ totals, items }: SlaAccuracyChartProps) {
  const averageRatio = totals.average_sla_within_target_ratio ?? 0
  const orderedItems = useMemo(
    () =>
      [...items].sort((a, b) =>
        (b.generated_at ?? '').localeCompare(a.generated_at ?? ''),
      ),
    [items],
  )

  return (
    <div className="space-y-4" data-testid="sla-accuracy-chart">
      <div>
        <p className="text-sm text-neutral-600">Average SLA accuracy</p>
        <div className="mt-2 h-3 w-full rounded-full bg-neutral-200 overflow-hidden">
          <div
            className="h-full bg-emerald-500 transition-all"
            style={{ width: formatPercent(Math.min(1, Math.max(0, averageRatio))) }}
          />
        </div>
        <p className="mt-1 text-xs text-neutral-500">
          {formatPercent(averageRatio)} of previewed stages met their SLA across the selected window.
        </p>
      </div>
      <ul className="space-y-3 text-sm">
        {orderedItems.map((item) => (
          <li
            key={item.preview_event_id}
            className="flex flex-col rounded-md border border-neutral-200 p-3"
          >
            <div className="flex items-center justify-between">
              <span className="font-medium text-neutral-700">
                Execution {item.execution_id.slice(0, 8)} • {item.stage_count} stages
              </span>
              <span className="text-xs text-neutral-500">
                {item.generated_at ? new Date(item.generated_at).toLocaleString() : 'Unknown'}
              </span>
            </div>
            <div className="mt-2 flex items-center gap-3">
              <div className="flex-1 h-2 rounded-full bg-neutral-100 overflow-hidden">
                <div
                  className="h-full bg-sky-500"
                  style={{ width: formatPercent(Math.min(1, Math.max(0, item.sla_within_target_ratio ?? 0))) }}
                />
              </div>
              <span className="text-xs text-neutral-600">
                {formatPercent(item.sla_within_target_ratio ?? 0)} on-time
              </span>
            </div>
            {item.mean_sla_delta_minutes !== null && item.mean_sla_delta_minutes !== undefined && (
              <p className="mt-1 text-xs text-neutral-500">
                Mean delta: {Math.round(item.mean_sla_delta_minutes)} minutes
              </p>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
