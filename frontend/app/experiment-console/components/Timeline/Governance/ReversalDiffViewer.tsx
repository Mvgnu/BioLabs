'use client'

import React from 'react'

import type { GovernanceOverrideReversalDetail } from '../../../../types'

export interface ReversalDiffViewerProps {
  reversal: GovernanceOverrideReversalDetail
}

const formatValue = (value: any) => {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch (error) {
      return String(value)
    }
  }
  return String(value)
}

const formatTimestamp = (value: string | null | undefined) => {
  if (!value) return null
  try {
    return new Intl.DateTimeFormat('en', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(value))
  } catch (error) {
    return value
  }
}

// purpose: render structured override reversal diffs alongside actor metadata
// inputs: reversal detail payload from governance timeline entries
// outputs: formatted diff list with attribution and cooldown context
// status: pilot
const ReversalDiffViewer = ({ reversal }: ReversalDiffViewerProps) => {
  const executedAt = formatTimestamp(reversal.created_at)
  const cooldownUntil = formatTimestamp(reversal.cooldown_expires_at)

  return (
    <section className="space-y-3">
      <header className="flex flex-col gap-1 text-sm text-neutral-600">
        <div className="font-semibold text-neutral-800">Override reversed</div>
        <div className="flex flex-wrap gap-2 text-xs text-neutral-500">
          {executedAt && <span>Executed {executedAt}</span>}
          {reversal.actor?.name && <span>by {reversal.actor.name}</span>}
          {cooldownUntil && <span>Cooldown until {cooldownUntil}</span>}
        </div>
      </header>
      <dl className="grid grid-cols-1 gap-2 text-sm">
        {reversal.diffs.length === 0 ? (
          <div className="text-neutral-500">No field changes detected.</div>
        ) : (
          reversal.diffs.map((diff) => (
            <div key={diff.key} className="space-y-1 rounded-md bg-white/60 p-2">
              <dt className="text-xs font-semibold uppercase text-neutral-500 tracking-wide">
                {diff.key}
              </dt>
              <dd className="text-xs text-neutral-600">
                <span className="font-medium text-neutral-700">Before:</span>{' '}
                {formatValue(diff.before)}
              </dd>
              <dd className="text-xs text-neutral-600">
                <span className="font-medium text-neutral-700">After:</span>{' '}
                {formatValue(diff.after)}
              </dd>
            </div>
          ))
        )}
      </dl>
    </section>
  )
}

export default ReversalDiffViewer
