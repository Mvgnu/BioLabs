'use client'

import React, { Fragment, useCallback, useMemo, useState } from 'react'

import type {
  GovernanceDecisionTimelineEntry,
  GovernanceOverrideLineageAggregates,
} from '../../../../types'
import { cn } from '../../../../utils/cn'
import ScenarioContextWidget from './Lineage/ScenarioContextWidget'
import AnalyticsLineageWidget from './Lineage/AnalyticsLineageWidget'
import ReversalDiffViewer from './ReversalDiffViewer'
import { useReverseGovernanceOverride } from '../../../../hooks/useExperimentConsole'

interface ReverseActionInput {
  recommendationId: string
  baselineId?: string | null
  notes: string
  cooldownMinutes: number | null
}

interface OverrideActionDetailProps {
  entry: GovernanceDecisionTimelineEntry
  detail: Record<string, any>
  reversalDetail: Record<string, any> | null
  onReverse: (input: ReverseActionInput) => Promise<void>
  isReversing: boolean
}

export interface GovernanceDecisionTimelineProps {
  entries: GovernanceDecisionTimelineEntry[]
  isLoading?: boolean
  isFetchingMore?: boolean
  hasMore?: boolean
  onLoadMore?: () => void
  executionId?: string | null
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
  const payload =
    detail && typeof detail.detail === 'object' ? detail.detail : detail ?? {}
  const entries = Object.entries(payload).filter(
    ([key]) =>
      !['lineage', 'lineage_summary', 'reversal_event', 'cooldown_expires_at'].includes(
        key,
      ),
  )
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

const OverrideActionDetail = ({
  entry,
  detail,
  reversalDetail,
  onReverse,
  isReversing,
}: OverrideActionDetailProps) => {
  const [showForm, setShowForm] = useState(false)
  const [notes, setNotes] = useState('')
  const [cooldownMinutes, setCooldownMinutes] = useState('30')
  const [error, setError] = useState<string | null>(null)

  const recommendationId =
    detail.recommendation_id || entry.detail?.recommendation_id || entry.rule_key
  const baselineId = detail.baseline_id || entry.baseline_id || null
  const reversible = Boolean(
    detail.reversible ?? entry.detail?.reversible ?? entry.detail?.detail?.reversible,
  )
  const cooldownUntil = detail.cooldown_expires_at || entry.detail?.cooldown_expires_at
  const cooldownDate = useMemo(() => {
    if (!cooldownUntil) return null
    const parsed = new Date(cooldownUntil)
    return Number.isNaN(parsed.getTime()) ? null : parsed
  }, [cooldownUntil])
  const isCoolingDown = Boolean(cooldownDate && cooldownDate.getTime() > Date.now())
  const canReverse =
    entry.entry_type === 'override_action' &&
    entry.status === 'executed' &&
    reversible &&
    !reversalDetail &&
    !isCoolingDown &&
    Boolean(recommendationId)

  const handleSubmit = async () => {
    if (!recommendationId) {
      setError('Recommendation context unavailable for reversal.')
      return
    }
    const trimmed = cooldownMinutes.trim()
    let parsedMinutes: number | null = null
    if (trimmed) {
      const numeric = Number(trimmed)
      if (!Number.isFinite(numeric) || numeric < 0) {
        setError('Cooldown minutes must be a non-negative number.')
        return
      }
      parsedMinutes = Math.round(numeric)
    }
    try {
      setError(null)
      await onReverse({
        recommendationId,
        baselineId,
        notes: notes.trim(),
        cooldownMinutes: parsedMinutes,
      })
      setShowForm(false)
      setNotes('')
    } catch (reverseError: any) {
      const detailMessage =
        reverseError?.response?.data?.detail ??
        reverseError?.message ??
        'Unable to reverse override.'
      setError(
        typeof detailMessage === 'string'
          ? detailMessage
          : 'Unable to reverse override.',
      )
    }
  }

  return (
    <div className="space-y-3">
      {reversalDetail && <ReversalDiffViewer reversal={reversalDetail} />}
      {isCoolingDown && (
        <p className="text-xs text-amber-600">
          Override reversal cooling down until {cooldownDate?.toLocaleString()}
        </p>
      )}
      {canReverse && (
        <div className="space-y-2">
          <button
            type="button"
            onClick={() => setShowForm((prev) => !prev)}
            className="text-xs font-semibold text-rose-600 border border-rose-200 bg-rose-50 hover:bg-rose-100 px-3 py-1 rounded-md"
          >
            {showForm ? 'Cancel reversal' : 'Reverse override'}
          </button>
          {showForm && (
            <div className="space-y-2 rounded-md border border-rose-100 bg-rose-50/60 p-3">
              <label className="flex flex-col gap-1 text-xs text-neutral-600">
                <span className="font-medium text-neutral-700">Reversal notes</span>
                <textarea
                  className="rounded-md border border-neutral-200 bg-white p-2 text-sm text-neutral-800"
                  rows={2}
                  value={notes}
                  onChange={(event) => setNotes(event.target.value)}
                  placeholder="Document why this override is being reversed"
                />
              </label>
              <label className="flex flex-col gap-1 text-xs text-neutral-600">
                <span className="font-medium text-neutral-700">Cooldown minutes</span>
                <input
                  type="number"
                  min={0}
                  className="rounded-md border border-neutral-200 bg-white p-2 text-sm text-neutral-800"
                  value={cooldownMinutes}
                  onChange={(event) => setCooldownMinutes(event.target.value)}
                />
              </label>
              {error && <p className="text-xs text-rose-600">{error}</p>}
              <div className="flex justify-end gap-2">
                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={isReversing}
                  className="text-xs font-semibold px-3 py-1 rounded-md bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-60"
                >
                  {isReversing ? 'Reversing…' : 'Confirm reversal'}
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
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
  executionId = null,
}: GovernanceDecisionTimelineProps) => {
  const reversalMutation = useReverseGovernanceOverride(executionId)

  const handleReverse = useCallback(
    async ({ recommendationId, baselineId, notes, cooldownMinutes }: ReverseActionInput) => {
      if (!executionId) {
        throw new Error('Execution context is required for reversals.')
      }
      const metadata: Record<string, any> = {
        source: 'experiment-console',
        reason: 'operator_request',
      }
      if (typeof cooldownMinutes === 'number') {
        metadata.cooldown_minutes = cooldownMinutes
      }
      await reversalMutation.mutateAsync({
        recommendationId,
        payload: {
          execution_id: executionId,
          baseline_id: baselineId ?? undefined,
          notes: notes || undefined,
          metadata,
        },
      })
    },
    [executionId, reversalMutation],
  )

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
              const analyticsSummary =
                entry.entry_type === 'analytics_snapshot'
                  ? (entry.detail?.lineage_summary as GovernanceOverrideLineageAggregates | undefined)
                  : null
              const detailPayload =
                entry.detail && typeof entry.detail.detail === 'object'
                  ? (entry.detail.detail as Record<string, any>)
                  : ((entry.detail as Record<string, any>) ?? {})
              const reversalDetail =
                (detailPayload.reversal_event as Record<string, any> | undefined) ||
                (entry.detail?.reversal_event as Record<string, any> | undefined) ||
                null
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
                  {analyticsSummary && (
                    <AnalyticsLineageWidget summary={analyticsSummary} />
                  )}
                  <div className="rounded-md border border-neutral-100 bg-neutral-50 p-3 space-y-3">
                    {renderDetail(entry.detail)}
                    {entry.entry_type === 'override_action' && (
                      <OverrideActionDetail
                        entry={entry}
                        detail={detailPayload}
                        reversalDetail={reversalDetail}
                        onReverse={handleReverse}
                        isReversing={reversalMutation.isPending}
                      />
                    )}
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
