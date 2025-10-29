'use client'

// purpose: summarise reviewer handoff context for guardrail workflows
// status: experimental

import React from 'react'

import { cn } from '../../utils/cn'

export interface GuardrailReviewerHandoffProps {
  reviewerName?: string | null
  reviewerEmail?: string | null
  reviewerRole?: string | null
  notes?: string | null
  pendingSince?: string | null
  onNotify?: () => void
  onClear?: () => void
}

export const GuardrailReviewerHandoff: React.FC<GuardrailReviewerHandoffProps> = ({
  reviewerName,
  reviewerEmail,
  reviewerRole,
  notes,
  pendingSince,
  onNotify,
  onClear,
}) => {
  const awaitingReviewer = !reviewerName && !reviewerEmail

  return (
    <section
      className={cn(
        'rounded-md border border-slate-200 bg-white p-4 shadow-sm',
        awaitingReviewer ? 'opacity-80' : 'opacity-100',
      )}
      data-testid="guardrail-reviewer-handoff"
    >
      <header className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold uppercase tracking-wide text-slate-500">Reviewer handoff</p>
          {awaitingReviewer ? (
            <p className="text-sm text-slate-600">No reviewer assigned yet. Route to governance lead.</p>
          ) : (
            <div className="text-sm text-slate-700">
              <p className="font-medium text-slate-900">{reviewerName}</p>
              {reviewerRole && <p className="text-xs uppercase tracking-wide text-slate-500">{reviewerRole}</p>}
              {reviewerEmail && (
                <a href={`mailto:${reviewerEmail}`} className="text-xs text-sky-600 hover:underline">
                  {reviewerEmail}
                </a>
              )}
            </div>
          )}
        </div>
        <div className="flex gap-2">
          {onNotify && (
            <button
              type="button"
              onClick={onNotify}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-800"
            >
              Notify reviewer
            </button>
          )}
          {onClear && (
            <button
              type="button"
              onClick={onClear}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
            >
              Clear
            </button>
          )}
        </div>
      </header>
      <div className="mt-3 space-y-2 text-xs text-slate-600">
        {notes && <p className="whitespace-pre-wrap">{notes}</p>}
        {pendingSince && (
          <p data-testid="guardrail-reviewer-pending">Pending since {new Date(pendingSince).toLocaleString()}</p>
        )}
      </div>
    </section>
  )
}

