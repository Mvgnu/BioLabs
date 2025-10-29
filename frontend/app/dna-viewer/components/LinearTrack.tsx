'use client'

// purpose: render linear genome track with guardrail-aware feature overlays
// status: experimental

import React, { type FC } from 'react'

import type { DNAViewerFeature } from '../../types'

export interface LinearTrackProps {
  sequenceLength: number
  features: DNAViewerFeature[]
}

export const LinearTrack: FC<LinearTrackProps> = ({ sequenceLength, features }) => {
  return (
    <div className="space-y-2">
      <div className="relative h-10 rounded border border-slate-200 bg-white">
        {features.map((feature) => {
          const startPct = ((feature.start - 1) / sequenceLength) * 100
          const widthPct = Math.max(((feature.end - feature.start + 1) / sequenceLength) * 100, 1)
          const severity = feature.guardrail_badges.some((badge) => badge.includes('review'))
          return (
            <div
              key={`${feature.label}-${feature.start}-${feature.end}`}
              className={`absolute top-1 h-8 rounded px-2 text-xs font-medium text-white flex items-center shadow ${
                severity ? 'bg-amber-500' : 'bg-sky-600'
              }`}
              style={{ left: `${startPct}%`, width: `${widthPct}%` }}
            >
              <span className="truncate">
                {feature.label} ({feature.feature_type})
              </span>
            </div>
          )
        })}
      </div>
      <div className="flex flex-wrap gap-2">
        {features.flatMap((feature) =>
          feature.guardrail_badges.map((badge) => (
            <span
              key={`${feature.label}-${badge}`}
              className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-700"
            >
              {badge}
            </span>
          )),
        )}
      </div>
    </div>
  )
}
