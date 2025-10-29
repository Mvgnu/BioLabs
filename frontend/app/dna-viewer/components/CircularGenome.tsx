'use client'

// purpose: render circular DNA overview with guardrail badges
// status: experimental
// depends_on: React

import React, { type FC } from 'react'

import type { DNAViewerFeature } from '../../types'

const polarToCartesian = (centerX: number, centerY: number, radius: number, angleInDegrees: number) => {
  const angleInRadians = ((angleInDegrees - 90) * Math.PI) / 180.0
  return {
    x: centerX + radius * Math.cos(angleInRadians),
    y: centerY + radius * Math.sin(angleInRadians),
  }
}

const describeArc = (
  x: number,
  y: number,
  radius: number,
  startAngle: number,
  endAngle: number,
) => {
  const start = polarToCartesian(x, y, radius, endAngle)
  const end = polarToCartesian(x, y, radius, startAngle)
  const largeArcFlag = endAngle - startAngle <= 180 ? '0' : '1'

  return ['M', start.x, start.y, 'A', radius, radius, 0, largeArcFlag, 0, end.x, end.y].join(' ')
}

const featureColor = (feature: DNAViewerFeature, index: number) => {
  if (feature.guardrail_badges.length) return '#f97316'
  const palette = ['#2563eb', '#059669', '#7c3aed', '#0ea5e9']
  return palette[index % palette.length]
}

export interface CircularGenomeProps {
  sequenceLength: number
  features: DNAViewerFeature[]
}

export const CircularGenome: FC<CircularGenomeProps> = ({ sequenceLength, features }) => {
  const radius = 140
  return (
    <svg viewBox="0 0 320 320" role="img" aria-label="Circular DNA map" className="w-full h-full">
      <circle cx={160} cy={160} r={radius} fill="none" stroke="#e5e7eb" strokeWidth={6} />
      {features.map((feature, index) => {
        const startAngle = ((feature.start - 1) / sequenceLength) * 360
        const endAngle = (feature.end / sequenceLength) * 360
        const color = featureColor(feature, index)
        return (
          <g key={`${feature.label}-${index}`}>
            <path
              d={describeArc(160, 160, radius - 4, startAngle, endAngle)}
              stroke={color}
              strokeWidth={8}
              fill="none"
              strokeLinecap="round"
            >
              <title>
                {feature.label} ({feature.feature_type}) [{feature.start}-{feature.end}]
                {feature.guardrail_badges.length ? ` • ${feature.guardrail_badges.join(', ')}` : ''}
              </title>
            </path>
          </g>
        )
      })}
      <text x={160} y={160} textAnchor="middle" className="fill-slate-600 text-sm">
        {sequenceLength.toLocaleString()} bp
      </text>
    </svg>
  )
}
