'use client'

// purpose: render a branch-aware timeline scrubber for cloning planner events
// status: experimental
// depends_on: frontend/app/hooks/useCloningPlanner, frontend/app/types

import React, { useEffect, useMemo, useState } from 'react'

import type {
  CloningPlannerEventPayload,
  CloningPlannerStageRecord,
} from '../../types'

interface TimelineEntry {
  cursor: string
  label: string
  timestamp: string
  type: string
  stage?: string
  branchId?: string | null
  guardrailActive: boolean
  details: string[]
}

interface PlannerTimelineProps {
  events: CloningPlannerEventPayload[]
  stageHistory: CloningPlannerStageRecord[]
  activeBranchId?: string | null
}

const formatTimestamp = (value: string): string => {
  try {
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) {
      return value
    }
    return date.toLocaleString()
  } catch (error) {
    return value
  }
}

export const PlannerTimeline: React.FC<PlannerTimelineProps> = ({
  events,
  stageHistory,
  activeBranchId,
}) => {
  const [selectedIndex, setSelectedIndex] = useState(0)

  const timeline = useMemo(() => {
    const historyByCursor = new Map<string, CloningPlannerStageRecord>()
    const timelineEntries: TimelineEntry[] = []
    stageHistory.forEach((record) => {
      if (record.timeline_position) {
        historyByCursor.set(record.timeline_position, record)
      }
    })

    const seenCursors = new Set<string>()

    events.forEach((event, index) => {
      const cursor = event.timeline_cursor ?? event.id ?? `${event.timestamp}-${index}`
      if (!cursor) {
        return
      }
      const record = historyByCursor.get(cursor)
      const guardrail = event.guardrail_transition?.current ?? event.guardrail_gate ?? {}
      const guardrailActive = Boolean(guardrail?.active)
      const stage = record?.stage ?? (event.payload?.stage as string | undefined)
      const details: string[] = []
      if (stage) {
        details.push(`Stage: ${stage}`)
      }
      if (guardrailActive) {
        const reasons = Array.isArray(guardrail?.reasons) ? guardrail.reasons.join(', ') : 'guardrail active'
        details.push(`Guardrail hold: ${reasons}`)
      }
      const checkpoint = event.checkpoint?.payload ?? {}
      if (checkpoint?.status) {
        details.push(`Status: ${checkpoint.status}`)
      }
      const custody = checkpoint?.guardrail?.custody ?? {}
      if (typeof custody.open_escalations === 'number' && custody.open_escalations > 0) {
        details.push(`Custody escalations: ${custody.open_escalations}`)
      }
      timelineEntries.push({
        cursor,
        label: record?.checkpoint_key ?? event.type,
        timestamp: event.timestamp,
        type: event.type,
        stage,
        branchId:
          ((event.branch?.active as string | undefined) ?? (record?.branch_id ?? activeBranchId ?? null)) || null,
        guardrailActive,
        details,
      })
      seenCursors.add(cursor)
    })

    stageHistory.forEach((record, index) => {
      const cursor = record.timeline_position ?? `${record.id}-${index}`
      if (seenCursors.has(cursor)) {
        return
      }
      const guardrail = record.guardrail_transition?.current ?? {}
      const guardrailActive = Boolean(guardrail?.active)
      const details: string[] = []
      details.push(`Stage: ${record.stage}`)
      if (guardrailActive) {
        const reasons = Array.isArray(guardrail?.reasons) ? guardrail.reasons.join(', ') : 'guardrail active'
        details.push(`Guardrail hold: ${reasons}`)
      }
      if (record.checkpoint_payload?.status) {
        details.push(`Status: ${record.checkpoint_payload.status}`)
      }
      timelineEntries.push({
        cursor,
        label: record.checkpoint_key ?? record.stage,
        timestamp: record.updated_at ?? record.completed_at ?? record.created_at ?? new Date().toISOString(),
        type: record.status,
        stage: record.stage,
        branchId: record.branch_id ?? activeBranchId ?? null,
        guardrailActive,
        details,
      })
    })

    timelineEntries.sort((left, right) => {
      const leftTime = new Date(left.timestamp).getTime()
      const rightTime = new Date(right.timestamp).getTime()
      if (Number.isNaN(leftTime) || Number.isNaN(rightTime)) {
        return left.cursor.localeCompare(right.cursor)
      }
      return leftTime - rightTime
    })

    return timelineEntries
  }, [events, stageHistory, activeBranchId])

  useEffect(() => {
    if (timeline.length === 0) {
      setSelectedIndex(0)
      return
    }
    setSelectedIndex(timeline.length - 1)
  }, [timeline.length])

  if (timeline.length === 0) {
    return (
      <div
        data-testid="planner-timeline-empty"
        className="rounded border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500"
      >
        Timeline will populate as planner events stream in.
      </div>
    )
  }

  const selected = timeline[Math.min(selectedIndex, timeline.length - 1)] ?? timeline[timeline.length - 1]

  return (
    <div className="space-y-4" data-testid="planner-timeline">
      <header className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-slate-800">Timeline replay</h3>
          <p className="text-xs text-slate-500">
            {selected?.stage ? `${selected.stage} · ` : ''}Captured {formatTimestamp(selected?.timestamp ?? '')}
          </p>
        </div>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
          {selected?.branchId ? `Branch ${selected.branchId}` : 'Primary branch'}
        </span>
      </header>

      <div className="flex items-center gap-3">
        <input
          type="range"
          min={0}
          max={timeline.length - 1}
          value={selectedIndex}
          onChange={(event) => setSelectedIndex(Number(event.target.value))}
          className="h-2 flex-1 cursor-pointer rounded-lg bg-slate-200"
          aria-label="Planner timeline scrubber"
          data-testid="planner-timeline-slider"
        />
        <span className="text-xs text-slate-500">{selectedIndex + 1} / {timeline.length}</span>
      </div>

      <ol className="space-y-3" data-testid="planner-event-log">
        {timeline.map((entry, index) => {
          const isActive = index === selectedIndex
          return (
            <li
              key={entry.cursor}
              className={`rounded border p-3 text-sm transition ${
                isActive
                  ? 'border-slate-500 bg-slate-50 shadow-sm'
                  : 'border-slate-200 bg-white hover:border-slate-300'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="font-semibold text-slate-800">{entry.label}</p>
                  <p className="text-xs text-slate-500">{formatTimestamp(entry.timestamp)}</p>
                </div>
                {entry.guardrailActive ? (
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-700">
                    Guardrail hold
                  </span>
                ) : (
                  <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-semibold text-emerald-700">
                    Clear
                  </span>
                )}
              </div>
              <p className="mt-1 text-xs text-slate-500">{entry.type}</p>
              {entry.details.length > 0 && (
                <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-slate-600">
                  {entry.details.map((detail) => (
                    <li key={detail}>{detail}</li>
                  ))}
                </ul>
              )}
              <button
                type="button"
                className="mt-3 text-xs font-semibold text-slate-600 underline"
                onClick={() => setSelectedIndex(index)}
                aria-label={`Select timeline event ${index + 1}`}
              >
                Scrub to event
              </button>
            </li>
          )
        })}
      </ol>
    </div>
  )
}

