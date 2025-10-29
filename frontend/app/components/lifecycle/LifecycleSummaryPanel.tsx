'use client'

// purpose: render aggregated lifecycle timeline summaries across planner, custody, dna, and sharing artifacts
// status: experimental

import React, { type FC, useMemo } from 'react'

import { useLifecycleNarrative } from '../../hooks/useLifecycleNarrative'
import type { LifecycleScope } from '../../types'

export interface LifecycleSummaryPanelProps {
  scope: LifecycleScope
  limit?: number
  title?: string
}

const formatDate = (value?: string | null): string => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString()
}

const guardrailSeverity = (metadata: Record<string, any>): 'neutral' | 'warning' | 'critical' => {
  const flags = metadata.guardrail_flags as string[] | undefined
  if (Array.isArray(flags) && flags.length > 0) {
    if (flags.some((flag) => flag.includes('halt') || flag.includes('critical'))) {
      return 'critical'
    }
    return 'warning'
  }
  return 'neutral'
}

export const LifecycleSummaryPanel: FC<LifecycleSummaryPanelProps> = ({ scope, limit = 100, title }) => {
  const query = useLifecycleNarrative(scope, { limit })
  const entries = query.data?.entries ?? []
  const summary = query.data?.summary
  const contextChips = summary?.context_chips ?? []

  const hasGuardrails = useMemo(() => {
    return entries.some((entry) => guardrailSeverity(entry.metadata) !== 'neutral')
  }, [entries])

  if (query.isLoading) {
    return (
      <section
        className="rounded border border-slate-200 bg-white p-4 shadow-sm"
        data-testid="lifecycle-summary-panel"
      >
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
          {title ?? 'Lifecycle timeline'}
        </h2>
        <p className="mt-2 text-sm text-slate-500">Loading lifecycle timeline…</p>
      </section>
    )
  }

  if (query.isError) {
    return (
      <section
        className="rounded border border-rose-200 bg-rose-50 p-4"
        data-testid="lifecycle-summary-panel"
      >
        <h2 className="text-sm font-semibold uppercase tracking-wide text-rose-500">
          {title ?? 'Lifecycle timeline'}
        </h2>
        <p className="mt-2 text-sm text-rose-600">Unable to load lifecycle timeline.</p>
      </section>
    )
  }

  return (
    <section
      className="space-y-6 rounded border border-slate-200 bg-white p-6 shadow-sm"
      data-testid="lifecycle-summary-panel"
    >
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-900">{title ?? 'Lifecycle timeline'}</h2>
          <p className="text-xs text-slate-500">
            {entries.length} events • latest update {formatDate(summary?.latest_event_at)}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {contextChips.map((chip) => (
            <span
              key={`${chip.kind ?? 'default'}:${chip.value}`}
              className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600"
            >
              {chip.label}: {chip.value}
            </span>
          ))}
        </div>
      </header>
      <div className="grid gap-4 md:grid-cols-4">
        <div className="rounded border border-slate-100 bg-slate-50 p-3">
          <p className="text-xs uppercase text-slate-500">Total events</p>
          <p className="text-xl font-semibold text-slate-900">{summary?.total_events ?? entries.length}</p>
        </div>
        <div className="rounded border border-slate-100 bg-slate-50 p-3">
          <p className="text-xs uppercase text-slate-500">Open escalations</p>
          <p className="text-xl font-semibold text-amber-600">{summary?.open_escalations ?? 0}</p>
        </div>
        <div className="rounded border border-slate-100 bg-slate-50 p-3">
          <p className="text-xs uppercase text-slate-500">Active guardrails</p>
          <p className="text-xl font-semibold text-rose-600">{summary?.active_guardrails ?? 0}</p>
        </div>
        <div className="rounded border border-slate-100 bg-slate-50 p-3">
          <p className="text-xs uppercase text-slate-500">Custody state</p>
          <p className="text-xl font-semibold text-slate-900">{summary?.custody_state ?? '—'}</p>
        </div>
      </div>
      {entries.length === 0 ? (
        <p className="text-sm text-slate-500">No lifecycle events recorded yet.</p>
      ) : (
        <ol className="space-y-4">
          {entries.map((entry) => {
            const severity = guardrailSeverity(entry.metadata)
            return (
              <li key={entry.entry_id} className="rounded border border-slate-100 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-slate-800">{entry.title}</p>
                    <p className="text-xs uppercase text-slate-400">{entry.source}</p>
                  </div>
                  <span
                    className={`rounded-full px-3 py-1 text-xs font-semibold ${
                      severity === 'critical'
                        ? 'bg-rose-100 text-rose-700'
                        : severity === 'warning'
                          ? 'bg-amber-100 text-amber-700'
                          : 'bg-slate-100 text-slate-600'
                    }`}
                  >
                    {entry.event_type}
                  </span>
                </div>
                <p className="mt-2 text-sm text-slate-600">{entry.summary ?? 'No summary provided.'}</p>
                <dl className="mt-3 grid gap-2 text-xs text-slate-500 md:grid-cols-3">
                  <div>
                    <dt className="font-semibold text-slate-400">Occurred</dt>
                    <dd>{formatDate(entry.occurred_at)}</dd>
                  </div>
                  <div>
                    <dt className="font-semibold text-slate-400">Checkpoint</dt>
                    <dd>{entry.metadata?.checkpoint_key ?? entry.metadata?.checkpoint ?? '—'}</dd>
                  </div>
                  <div>
                    <dt className="font-semibold text-slate-400">Guardrail flags</dt>
                    <dd>
                      {Array.isArray(entry.metadata?.guardrail_flags) && entry.metadata.guardrail_flags.length > 0
                        ? entry.metadata.guardrail_flags.join(', ')
                        : 'None'}
                    </dd>
                  </div>
                </dl>
              </li>
            )
          })}
        </ol>
      )}
      {hasGuardrails ? (
        <p className="text-xs text-amber-600">
          Guardrail activity detected. Review mitigation timelines to ensure readiness before resuming downstream workflows.
        </p>
      ) : null}
    </section>
  )
}

