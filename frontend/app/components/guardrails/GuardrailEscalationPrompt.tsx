'use client'

// purpose: highlight guardrail escalations with acknowledgement controls
// status: experimental

import React from 'react'

import { cn } from '../../utils/cn'

type GuardrailEscalationSeverity = 'info' | 'review' | 'critical'

export interface GuardrailEscalationPromptProps {
  severity?: GuardrailEscalationSeverity
  title?: string
  message: string
  metadata?: Record<string, any> | null
  actionLabel?: string
  onAcknowledge?: () => void
}

const SEVERITY_THEME: Record<GuardrailEscalationSeverity, { surface: string; accent: string; text: string }> = {
  info: {
    surface: 'border-sky-200 bg-sky-50',
    accent: 'bg-sky-500',
    text: 'text-sky-900',
  },
  review: {
    surface: 'border-amber-200 bg-amber-50',
    accent: 'bg-amber-500',
    text: 'text-amber-900',
  },
  critical: {
    surface: 'border-rose-200 bg-rose-50',
    accent: 'bg-rose-500',
    text: 'text-rose-900',
  },
}

export const GuardrailEscalationPrompt: React.FC<GuardrailEscalationPromptProps> = ({
  severity = 'review',
  title = 'Guardrail escalation',
  message,
  metadata,
  actionLabel = 'Acknowledge',
  onAcknowledge,
}) => {
  const theme = SEVERITY_THEME[severity]

  return (
    <div className={cn('rounded-md border p-4 shadow-sm', theme.surface)} data-testid="guardrail-escalation">
      <div className="flex items-start gap-3">
        <span className={cn('mt-1 h-2.5 w-2.5 rounded-full', theme.accent)} aria-hidden />
        <div className="flex-1 space-y-2">
          <header>
            <p className={cn('text-sm font-semibold uppercase tracking-wide', theme.text)}>{title}</p>
            <p className="text-sm text-slate-700">{message}</p>
          </header>
          {metadata && Object.keys(metadata).length > 0 && (
            <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs text-slate-600">
              {Object.entries(metadata).map(([key, value]) => (
                <div key={key} className="flex flex-col gap-0.5">
                  <dt className="font-semibold uppercase tracking-wide text-slate-500">{key}</dt>
                  <dd className="font-mono text-[11px] text-slate-700 break-all">
                    {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                  </dd>
                </div>
              ))}
            </dl>
          )}
        </div>
        {onAcknowledge && (
          <button
            type="button"
            onClick={onAcknowledge}
            className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-800"
          >
            {actionLabel}
          </button>
        )}
      </div>
    </div>
  )
}

