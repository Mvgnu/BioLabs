'use client'

// purpose: render guardrail status badge with severity-aware styling and metadata tags
// status: experimental

import React from 'react'

import { cn } from '../../utils/cn'

export interface GuardrailBadgeProps {
  label: string
  state?: string | null
  detail?: string | null
  metadataTags?: string[]
}

const STATE_THEME: Record<string, { surface: string; badge: string; dot: string; text: string }> = {
  ok: {
    surface: 'border-emerald-200 bg-emerald-50',
    badge: 'bg-emerald-600 text-emerald-50',
    dot: 'bg-emerald-500',
    text: 'text-emerald-900',
  },
  review: {
    surface: 'border-amber-200 bg-amber-50',
    badge: 'bg-amber-600 text-amber-50',
    dot: 'bg-amber-500',
    text: 'text-amber-900',
  },
  blocked: {
    surface: 'border-rose-200 bg-rose-50',
    badge: 'bg-rose-600 text-rose-50',
    dot: 'bg-rose-500',
    text: 'text-rose-900',
  },
  breach: {
    surface: 'border-rose-200 bg-rose-50',
    badge: 'bg-rose-600 text-rose-50',
    dot: 'bg-rose-500',
    text: 'text-rose-900',
  },
}

const normaliseState = (state?: string | null): string => {
  if (!state) return 'unknown'
  return state.toLowerCase().replace(/[^a-z0-9]+/g, '_')
}

const formatStateLabel = (state: string): string => {
  if (!state) return 'unknown'
  return state
    .split('_')
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ')
}

export const GuardrailBadge: React.FC<GuardrailBadgeProps> = ({
  label,
  state,
  detail,
  metadataTags,
}) => {
  const normalised = normaliseState(state)
  const theme = STATE_THEME[normalised] ?? {
    surface: 'border-slate-200 bg-slate-50',
    badge: 'bg-slate-500 text-white',
    dot: 'bg-slate-400',
    text: 'text-slate-800',
  }

  return (
    <div
      className={cn('flex flex-col gap-2 rounded-md border px-3 py-2 transition-colors', theme.surface)}
      data-testid="guardrail-badge"
    >
      <div className="flex items-center gap-2">
        <span className={cn('h-2 w-2 rounded-full', theme.dot)} aria-hidden />
        <span className={cn('text-sm font-semibold', theme.text)}>{label}</span>
        <span className={cn('rounded-full px-2 py-0.5 text-xs font-semibold uppercase tracking-wide', theme.badge)}>
          {formatStateLabel(normalised)}
        </span>
      </div>
      {detail && <p className="text-xs text-slate-600">{detail}</p>}
      {metadataTags && metadataTags.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {metadataTags.map((tag) => (
            <span key={tag} className="rounded-full bg-white/70 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-slate-500">
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

