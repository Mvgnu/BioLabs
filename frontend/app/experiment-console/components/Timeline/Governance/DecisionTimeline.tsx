'use client'

import React, { Fragment } from 'react'

import type { GovernanceDecisionTimelineEntry } from '../../../../types'
import { cn } from '../../../../utils/cn'
import ScenarioContextWidget from './Lineage/ScenarioContextWidget'

export interface GovernanceDecisionTimelineProps {
  entries: GovernanceDecisionTimelineEntry[]
  isLoading?: boolean
  isFetchingMore?: boolean
  hasMore?: boolean
  onLoadMore?: () => void
}

const entryBadgeStyles: Record<string, string> = {
  override_recommendation: 'bg-blue-50 text-blue-700 border-blue-200',
  override_action: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  baseline_event: 'bg-amber-50 text-amber-700 border-amber-200',
  analytics_snapshot: 'bg-purple-50 text-purple-700 border-purple-200',
  coaching_note: 'bg-slate-50 text-slate-700 border-slate-200',
}

const typeLabels: Record<string, string> = {
  override_recommendation: 'Override Recommendation',
  override_action: 'Override Outcome',
  baseline_event: 'Baseline Event',
  analytics_snapshot: 'Analytics Snapshot',
  coaching_note: 'Coaching Note',
}

const formatTimestamp = (value: string) => {
  try {
    return new Intl.DateTimeFormat('en', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(value))
  } catch (error) {
    return value
  }
}

const renderDetail = (detail: Record<string, any>) => {
  const entries = Object.entries(detail ?? {}).filter(([key]) => key !== 'lineage')
  if (entries.length === 0) {
    return <p className="text-sm text-neutral-500">No supplemental detail available.</p>
  }
  return (
    <dl className="grid grid-cols-1 gap-1 text-sm text-neutral-700">
      {entries.slice(0, 6).map(([key, raw]) => (
        <Fragment key={key}>
          <dt className="font-medium text-neutral-600">{key}</dt>
          <dd className="text-neutral-800">
            {typeof raw === 'object' ? JSON.stringify(raw) : String(raw)}
          </dd>
        </Fragment>
      ))}
    </dl>
  )
}

// purpose: render governance decision feed blending override, baseline, and analytics insights
// inputs: paginated entries, loading states, load-more callback
// outputs: governance timeline cards for experiment console sidebar
// status: pilot
const GovernanceDecisionTimeline = ({
  entries,
  isLoading = false,
  isFetchingMore = false,
  hasMore = false,
  onLoadMore,
}: GovernanceDecisionTimelineProps) => {
  if (isLoading && entries.length === 0) {
    return (
      <div className="border border-neutral-200 rounded-lg bg-white shadow-sm p-4 space-y-2">
        <p className="text-sm text-neutral-600">Loading governance activity…</p>
      </div>
    )
  }

  return (
    <div className="border border-neutral-200 rounded-lg bg-white shadow-sm divide-y divide-neutral-100">
      <header className="p-4">
        <h2 className="text-lg font-semibold text-neutral-900">Governance Decisions</h2>
        <p className="text-sm text-neutral-600">
          Composite feed of recommendations, overrides, baseline transitions, and cadence analytics.
        </p>
      </header>
      <div className="max-h-[560px] overflow-y-auto">
        {entries.length === 0 ? (
          <div className="p-4 text-sm text-neutral-600">No governance activity captured yet.</div>
        ) : (
          <ul className="divide-y divide-neutral-100">
            {entries.map((entry) => {
              const badgeStyle = entryBadgeStyles[entry.entry_type] ?? 'bg-slate-50 text-slate-700 border-slate-200'
              const label = typeLabels[entry.entry_type] ?? entry.entry_type
              return (
                <li key={entry.entry_id} className="p-4 space-y-2">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <span className={cn('inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold', badgeStyle)}>
                        {label}
                      </span>
                      {entry.summary && (
                        <p className="mt-2 text-sm font-medium text-neutral-900">{entry.summary}</p>
                      )}
                      <p className="text-xs text-neutral-500 mt-1">
                        Logged {formatTimestamp(entry.occurred_at)}
                        {entry.actor?.name ? ` • ${entry.actor.name}` : ''}
                      </p>
                    </div>
                    {entry.status && (
                      <span className="text-xs font-semibold uppercase text-neutral-500">{entry.status}</span>
                    )}
                  </div>
                  {entry.rule_key && (
                    <p className="text-xs uppercase tracking-wide text-neutral-500">Rule {entry.rule_key}</p>
                  )}
                  {entry.lineage && <ScenarioContextWidget lineage={entry.lineage} />}
                  <div className="rounded-md border border-neutral-100 bg-neutral-50 p-3">
                    {renderDetail(entry.detail)}
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>
      {hasMore && onLoadMore && (
        <div className="p-4">
          <button
            type="button"
            onClick={onLoadMore}
            disabled={isFetchingMore}
            className="w-full text-sm font-medium rounded-md border border-neutral-200 bg-neutral-50 py-2 text-neutral-700 hover:bg-neutral-100 transition-colors disabled:opacity-60"
          >
            {isFetchingMore ? 'Loading more…' : 'Load more decisions'}
          </button>
        </div>
      )}
    </div>
  )
}

export default GovernanceDecisionTimeline
