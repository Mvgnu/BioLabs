'use client'

import React, { Fragment } from 'react'
import clsx from 'clsx'
import type {
  BaselineReviewDecision,
  GovernanceBaselineVersion,
} from '../../../types'

interface BaselineReviewerQueueProps {
  baselines: GovernanceBaselineVersion[]
  selectedId?: string | null
  onSelect: (baselineId: string) => void
  onReview: (baselineId: string, payload: BaselineReviewDecision) => void
  onPublish: (baselineId: string, notes?: string | null) => void
  onRollback: (baselineId: string, reason: string) => void
  canManage: boolean
  currentUserId?: string | null
}

const statusColor: Record<string, string> = {
  submitted: 'bg-amber-100 text-amber-700',
  approved: 'bg-emerald-100 text-emerald-700',
  rejected: 'bg-rose-100 text-rose-700',
  published: 'bg-sky-100 text-sky-700',
  rolled_back: 'bg-neutral-200 text-neutral-700',
}

// purpose: render reviewer queue with lifecycle actions mapped to governance baselines
// inputs: baseline collection, action callbacks, RBAC flags
// outputs: interactive list enabling approvals, publication, and rollbacks
// status: pilot
export default function BaselineReviewerQueue({
  baselines,
  selectedId,
  onSelect,
  onReview,
  onPublish,
  onRollback,
  canManage,
  currentUserId,
}: BaselineReviewerQueueProps) {
  if (!baselines.length) {
    return (
      <section className="border border-dashed border-neutral-300 rounded-lg p-6 text-center text-sm text-neutral-500">
        No baseline submissions yet. Draft a proposal to begin governance review.
      </section>
    )
  }

  const canReview = (baseline: GovernanceBaselineVersion) => {
    if (!canManage) return false
    if (!currentUserId) return true
    if (baseline.reviewer_ids.includes(currentUserId)) return true
    return canManage
  }

  const requestInput = (label: string) => {
    if (typeof window === 'undefined') return null
    const response = window.prompt(label)
    if (response === null) return null
    return response.trim()
  }

  const triggerReview = (baseline: GovernanceBaselineVersion, decision: 'approve' | 'reject') => {
    const notes = canManage ? requestInput('Add review notes (optional):') : null
    onReview(baseline.id, { decision, notes: notes || undefined })
  }

  const triggerPublish = (baseline: GovernanceBaselineVersion) => {
    const notes = requestInput('Add publish notes (optional):')
    onPublish(baseline.id, notes || undefined)
  }

  const triggerRollback = (baseline: GovernanceBaselineVersion) => {
    const reason = requestInput('Describe why the baseline is being rolled back:')
    if (!reason) return
    onRollback(baseline.id, reason)
  }

  return (
    <section className="space-y-3">
      {baselines.map((baseline) => {
        const active = baseline.id === selectedId
        const tags = baseline.labels ?? []
        const statusClass = statusColor[baseline.status] ?? statusColor.submitted
        return (
          <article
            key={baseline.id}
            className={clsx(
              'border rounded-lg p-4 bg-white shadow-sm transition',
              active ? 'border-primary-300 ring-2 ring-primary-200' : 'border-neutral-200',
            )}
          >
            <header className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
              <div className="space-y-1">
                <button
                  type="button"
                  onClick={() => onSelect(baseline.id)}
                  className="text-left text-lg font-semibold text-neutral-900 hover:text-primary-700"
                >
                  {baseline.name}
                </button>
                <p className="text-xs text-neutral-500">
                  Submitted {new Date(baseline.submitted_at).toLocaleString()}
                </p>
                <p className="text-sm text-neutral-600 whitespace-pre-wrap">
                  {baseline.description || 'No submission summary provided.'}
                </p>
              </div>
              <span className={clsx('self-start text-xs font-semibold px-3 py-1 rounded-full', statusClass)}>
                {baseline.status.replace('_', ' ')}
              </span>
            </header>

            <div className="mt-3 flex flex-wrap gap-2">
              {tags.map((label) => (
                <span
                  key={`${baseline.id}-${label.key}-${label.value}`}
                  className="text-xs uppercase tracking-wide px-2 py-1 rounded-full bg-neutral-100 text-neutral-700"
                >
                  {label.key}: {label.value}
                </span>
              ))}
            </div>

            <div className="mt-4 flex flex-wrap gap-3">
              <div className="text-xs text-neutral-500">
                Reviewers:{' '}
                {baseline.reviewer_ids.length ? baseline.reviewer_ids.join(', ') : 'Unassigned'}
              </div>
              {baseline.version_number && (
                <div className="text-xs text-neutral-500">Version {baseline.version_number}</div>
              )}
              {baseline.is_current && (
                <div className="text-xs font-semibold text-emerald-600">Current production baseline</div>
              )}
            </div>

            {canManage && (
              <div className="mt-4 flex flex-wrap gap-2">
                {baseline.status === 'submitted' && canReview(baseline) && (
                  <Fragment>
                    <button
                      type="button"
                      onClick={() => triggerReview(baseline, 'approve')}
                      className="text-xs font-semibold px-3 py-2 rounded-md bg-emerald-600 text-white hover:bg-emerald-700"
                    >
                      Approve
                    </button>
                    <button
                      type="button"
                      onClick={() => triggerReview(baseline, 'reject')}
                      className="text-xs font-semibold px-3 py-2 rounded-md bg-rose-600 text-white hover:bg-rose-700"
                    >
                      Reject
                    </button>
                  </Fragment>
                )}
                {baseline.status === 'approved' && (
                  <button
                    type="button"
                    onClick={() => triggerPublish(baseline)}
                    className="text-xs font-semibold px-3 py-2 rounded-md bg-sky-600 text-white hover:bg-sky-700"
                  >
                    Publish baseline
                  </button>
                )}
                {baseline.status === 'published' && (
                  <button
                    type="button"
                    onClick={() => triggerRollback(baseline)}
                    className="text-xs font-semibold px-3 py-2 rounded-md bg-neutral-800 text-white hover:bg-neutral-900"
                  >
                    Roll back
                  </button>
                )}
              </div>
            )}
          </article>
        )
      })}
    </section>
  )
}
