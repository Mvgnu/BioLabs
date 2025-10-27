'use client'

import React from 'react'
import type { GovernanceBaselineEvent } from '../../../types'

interface BaselineTimelineProps {
  events: GovernanceBaselineEvent[]
  baselineName?: string
}

// purpose: visualize baseline lifecycle history for reviewers and admins
// inputs: ordered baseline events from governance API
// outputs: chronological list summarizing state transitions
// status: pilot
export default function BaselineTimeline({ events, baselineName }: BaselineTimelineProps) {
  if (!events.length) {
    return (
      <section className="border border-neutral-200 rounded-lg bg-white shadow-sm p-4 text-sm text-neutral-500">
        No lifecycle events recorded yet. Actions taken here will populate an audit trail automatically.
      </section>
    )
  }

  return (
    <section className="border border-neutral-200 rounded-lg bg-white shadow-sm p-4 space-y-4">
      <header className="space-y-1">
        <p className="text-xs uppercase tracking-wide text-neutral-500">Lifecycle History</p>
        <h3 className="text-lg font-semibold text-neutral-900">{baselineName ?? 'Baseline'} timeline</h3>
      </header>
      <ol className="space-y-3">
        {events.map((event) => (
          <li key={event.id} className="border-l-2 border-primary-300 pl-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-semibold text-neutral-800">{event.action.replace('_', ' ')}</span>
              <span className="text-xs text-neutral-500">{new Date(event.created_at).toLocaleString()}</span>
            </div>
            {event.notes && <p className="text-sm text-neutral-600 mt-1">{event.notes}</p>}
            {event.detail && Object.keys(event.detail).length > 0 && (
              <dl className="mt-2 grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-neutral-500">
                {Object.entries(event.detail).slice(0, 6).map(([key, value]) => (
                  <div key={`${event.id}-${key}`}>
                    <dt className="font-medium text-neutral-600">{key}</dt>
                    <dd className="text-neutral-700">
                      {typeof value === 'string' ? value : JSON.stringify(value)}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </li>
        ))}
      </ol>
    </section>
  )
}
