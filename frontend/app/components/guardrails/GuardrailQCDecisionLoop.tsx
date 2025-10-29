'use client'

// purpose: present QC artifact guardrail loop with reviewer decisions and breach metrics
// status: experimental

import React from 'react'

import type { CloningPlannerQCArtifact } from '../../types'
import { cn } from '../../utils/cn'

export interface GuardrailQCDecisionLoopProps {
  artifacts: CloningPlannerQCArtifact[]
  onAcknowledge?: (artifact: CloningPlannerQCArtifact) => void
}

const formatMetricValue = (value: unknown): string => {
  if (value == null) return '—'
  if (typeof value === 'number') return value.toFixed(2)
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

export const GuardrailQCDecisionLoop: React.FC<GuardrailQCDecisionLoopProps> = ({
  artifacts,
  onAcknowledge,
}) => {
  if (!artifacts.length) {
    return (
      <div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
        No QC artifacts recorded yet.
      </div>
    )
  }

  return (
    <div className="space-y-3" data-testid="guardrail-qc-loop">
      {artifacts.map((artifact) => {
        const metrics = artifact.metrics ?? {}
        const thresholds = artifact.thresholds ?? {}
        return (
          <article
            key={artifact.id}
            className="rounded-md border border-slate-200 bg-white p-4 shadow-sm"
          >
            <header className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-slate-900">
                  {artifact.artifact_name ?? 'QC Artifact'}
                </p>
                <p className="text-xs uppercase tracking-wide text-slate-500">
                  Sample {artifact.sample_id ?? 'unknown'}
                </p>
              </div>
              <div className="text-right text-xs text-slate-500">
                {artifact.reviewer_decision ? (
                  <span
                    className={cn(
                      'rounded-full px-2 py-0.5 font-semibold uppercase tracking-wide',
                      artifact.reviewer_decision === 'approved'
                        ? 'bg-emerald-100 text-emerald-700'
                        : 'bg-rose-100 text-rose-700',
                    )}
                  >
                    {artifact.reviewer_decision}
                  </span>
                ) : (
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 font-semibold uppercase tracking-wide text-amber-700">
                    pending
                  </span>
                )}
                {artifact.reviewer_notes && (
                  <p className="mt-1 text-[11px] text-slate-500">{artifact.reviewer_notes}</p>
                )}
              </div>
            </header>

            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Metrics</h3>
                <dl className="mt-1 space-y-1 text-xs text-slate-700">
                  {Object.entries(metrics).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between gap-2">
                      <dt className="font-medium text-slate-600">{key}</dt>
                      <dd className="font-mono text-[11px]">{formatMetricValue(value)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Thresholds</h3>
                <dl className="mt-1 space-y-1 text-xs text-slate-700">
                  {Object.entries(thresholds).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between gap-2">
                      <dt className="font-medium text-slate-600">{key}</dt>
                      <dd className="font-mono text-[11px]">{formatMetricValue(value)}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            </div>

            {onAcknowledge && (
              <div className="mt-3 flex justify-end">
                <button
                  type="button"
                  onClick={() => onAcknowledge(artifact)}
                  className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
                >
                  Acknowledge review
                </button>
              </div>
            )}
          </article>
        )
      })}
    </div>
  )
}

