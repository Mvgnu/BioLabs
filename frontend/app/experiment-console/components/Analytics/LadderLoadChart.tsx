import React, { useMemo } from 'react'

import type { GovernanceAnalyticsPreviewSummary } from '../../../types'

interface LadderLoadChartProps {
  items: GovernanceAnalyticsPreviewSummary[]
}

// purpose: highlight governance ladder load, overrides, and risk posture per preview
// status: pilot

const loadMeterWidth = (load: number) => `${Math.min(100, Math.round(load * 12))}%`

export default function LadderLoadChart({ items }: LadderLoadChartProps) {
  const aggregates = useMemo(() => {
    if (!items.length) {
      return { average: 0 }
    }
    const totalLoad = items.reduce((sum, item) => sum + item.ladder_load, 0)
    return { average: totalLoad / items.length }
  }, [items])

  if (!items.length) {
    return (
      <p className="text-sm text-neutral-500" data-testid="ladder-load-empty">
        Run a preview to populate ladder load analytics.
      </p>
    )
  }

  return (
    <div className="space-y-3" data-testid="ladder-load-chart">
      <p className="text-sm text-neutral-600">
        Average ladder load: {aggregates.average.toFixed(1)} stages + overrides per preview.
      </p>
      <ul className="space-y-2">
        {items.map((item) => (
          <li
            key={item.preview_event_id}
            className="rounded-md border border-neutral-200 p-3"
          >
            <div className="flex items-center justify-between text-sm text-neutral-700">
              <span>
                Execution {item.execution_id.slice(0, 8)} • Executed overrides {item.override_actions_executed}
                {item.override_actions_reversed > 0
                  ? ` · Reversed ${item.override_actions_reversed}`
                  : ''}
              </span>
              <span className="text-xs uppercase tracking-wide text-neutral-500">
                Risk: {item.risk_level}
              </span>
            </div>
            <div className="mt-2 h-2 rounded-full bg-neutral-100 overflow-hidden">
              <div
                className="h-full bg-indigo-500"
                style={{ width: loadMeterWidth(item.ladder_load) }}
              />
            </div>
            <div className="mt-1 flex items-center justify-between text-xs text-neutral-500">
              <span>{item.ladder_load.toFixed(1)} ladder load</span>
              <span>
                {Math.round((item.blocked_ratio ?? 0) * 100)}% blocked
                {typeof item.override_cooldown_minutes === 'number' &&
                Number.isFinite(item.override_cooldown_minutes)
                  ? ` · Cooldown ${Math.round(item.override_cooldown_minutes)}m`
                  : ''}
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
