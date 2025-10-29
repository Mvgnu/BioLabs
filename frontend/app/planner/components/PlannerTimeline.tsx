'use client'

// purpose: render a branch-aware timeline scrubber for cloning planner events
// status: experimental
// depends_on: frontend/app/hooks/useCloningPlanner, frontend/app/types

import React, { useEffect, useMemo, useState } from 'react'

import type {
  CloningPlannerBranchComparison,
  CloningPlannerBranchCustodyDeltas,
  CloningPlannerBranchCustodyMetrics,
  CloningPlannerBranchLineageDelta,
  CloningPlannerEventPayload,
  CloningPlannerMitigationHint,
  CloningPlannerCheckpointCustodySummary,
  CloningPlannerRecoveryBundle,
  CloningPlannerResumeToken,
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
  branchLineage?: CloningPlannerBranchLineageDelta | null
  branchComparison?: CloningPlannerBranchComparison | null
  mitigationHints: CloningPlannerMitigationHint[]
  resumeToken?: CloningPlannerResumeToken | null
  recoveryContext?: Record<string, any> | null
  recoveryBundle?: CloningPlannerRecoveryBundle | null
}

interface PlannerTimelineProps {
  events: CloningPlannerEventPayload[]
  stageHistory: CloningPlannerStageRecord[]
  activeBranchId?: string | null
  replayWindow?: CloningPlannerStageRecord[]
  comparisonWindow?: CloningPlannerStageRecord[]
  mitigationHints?: CloningPlannerMitigationHint[]
  recoveryBundle?: CloningPlannerRecoveryBundle | null
  onResume?: (token: CloningPlannerResumeToken) => void
  resumePending?: boolean
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

const MITIGATION_LINKS: Record<string, string> = {
  custody: '/docs/operations/custody_governance.md',
  qc: '/docs/operations/custody_governance.md#qc-resolution',
  primers: '/docs/planning/cloning_planner_scope.md#primer-guardrails',
  guardrail: '/docs/planning/cloning_planner_scope.md#guardrail-gate',
}

const resolveHintLink = (hint: CloningPlannerMitigationHint): string | undefined => {
  return MITIGATION_LINKS[hint.category] ?? undefined
}

const formatComparisonDelta = (
  comparison: CloningPlannerBranchComparison | null | undefined,
): string | null => {
  if (!comparison || typeof comparison.history_delta !== 'number') {
    return null
  }
  const formatted = comparison.history_delta > 0 ? `+${comparison.history_delta}` : `${comparison.history_delta}`
  const reference = comparison.reference_branch_id
    ? `branch ${comparison.reference_branch_id.slice(0, 8)}`
    : 'reference'
  return `${formatted} vs ${reference}`
}

const collectComparisonDetails = (
  comparison: CloningPlannerBranchComparison | null | undefined,
): string[] => {
  if (!comparison) {
    return []
  }
  const details: string[] = []
  const formatSeverityLabel = (value?: string | null): string | null => {
    if (!value) {
      return null
    }
    return value.toUpperCase()
  }
  if (typeof comparison.history_delta === 'number' && comparison.history_delta !== 0) {
    details.push(`History delta: ${comparison.history_delta}`)
  }
  if (Array.isArray(comparison.ahead_checkpoints) && comparison.ahead_checkpoints.length > 0) {
    const stages = comparison.ahead_checkpoints
      .map((entry) => entry?.stage ?? entry?.checkpoint_key ?? `#${entry?.index}`)
      .filter(Boolean)
    if (stages.length > 0) {
      details.push(`Ahead of reference: ${stages.join(', ')}`)
    }
  }
  if (Array.isArray(comparison.missing_checkpoints) && comparison.missing_checkpoints.length > 0) {
    const stages = comparison.missing_checkpoints
      .map((entry) => entry?.stage ?? entry?.checkpoint_key ?? `#${entry?.index}`)
      .filter(Boolean)
    if (stages.length > 0) {
      details.push(`Missing from branch: ${stages.join(', ')}`)
    }
  }
  if (Array.isArray(comparison.divergent_stages) && comparison.divergent_stages.length > 0) {
    comparison.divergent_stages.forEach((divergence) => {
      const stage = divergence?.primary?.stage ?? divergence?.reference?.stage ?? `#${divergence?.index}`
      const referenceGate = divergence?.reference?.guardrail_state
      if (stage) {
        details.push(
          referenceGate
            ? `Divergent at ${stage} (reference gate: ${referenceGate})`
            : `Divergent at ${stage}`,
        )
      }
      const primaryCustody = divergence?.primary?.custody_summary as
        | CloningPlannerCheckpointCustodySummary
        | undefined
      const referenceCustody = divergence?.reference?.custody_summary as
        | CloningPlannerCheckpointCustodySummary
        | undefined
      const primarySeverity = formatSeverityLabel(primaryCustody?.max_severity)
      const referenceSeverity = formatSeverityLabel(referenceCustody?.max_severity)
      if (primarySeverity || referenceSeverity) {
        details.push(
          `Custody severity at ${stage}: ${primarySeverity ?? 'CLEAR'} vs ${referenceSeverity ?? 'CLEAR'}`,
        )
      }
      if ((referenceCustody?.open_drill_count ?? 0) > 0) {
        details.push(`Reference drills active at ${stage}: ${referenceCustody?.open_drill_count}`)
      }
      if ((referenceCustody?.open_escalations ?? 0) > 0) {
        details.push(`Reference escalations at ${stage}: ${referenceCustody?.open_escalations}`)
      }
    })
  }
  const primaryMetrics = comparison.primary_custody_metrics as CloningPlannerBranchCustodyMetrics | undefined
  const referenceMetrics = comparison.reference_custody_metrics as CloningPlannerBranchCustodyMetrics | undefined
  const primarySeverity = formatSeverityLabel(primaryMetrics?.max_severity)
  const referenceSeverity = formatSeverityLabel(referenceMetrics?.max_severity)
  if (primarySeverity || referenceSeverity) {
    details.push(
      `Branch severity: ${primarySeverity ?? 'CLEAR'} vs ${referenceSeverity ?? 'CLEAR'}`,
    )
  }
  const formatDelta = (value: number): string => (value > 0 ? `+${value}` : `${value}`)
  const custodyDeltas = comparison.custody_deltas as CloningPlannerBranchCustodyDeltas | undefined
  if (custodyDeltas) {
    if (typeof custodyDeltas.severity_delta === 'number' && custodyDeltas.severity_delta !== 0) {
      details.push(
        custodyDeltas.severity_delta > 0
          ? `Primary branch severity elevated (+${custodyDeltas.severity_delta})`
          : `Reference branch severity elevated (${custodyDeltas.severity_delta})`,
      )
    }
    if (
      typeof custodyDeltas.open_drill_delta === 'number' &&
      custodyDeltas.open_drill_delta !== 0
    ) {
      details.push(`Open drill delta: ${formatDelta(custodyDeltas.open_drill_delta)}`)
    }
    if (
      typeof custodyDeltas.open_escalation_delta === 'number' &&
      custodyDeltas.open_escalation_delta !== 0
    ) {
      details.push(`Open escalation delta: ${formatDelta(custodyDeltas.open_escalation_delta)}`)
    }
    if (
      typeof custodyDeltas.pending_event_delta === 'number' &&
      custodyDeltas.pending_event_delta !== 0
    ) {
      details.push(`Pending drill delta: ${formatDelta(custodyDeltas.pending_event_delta)}`)
    }
    if (
      typeof custodyDeltas.blocked_checkpoint_delta === 'number' &&
      custodyDeltas.blocked_checkpoint_delta !== 0
    ) {
      details.push(`Blocked checkpoint delta: ${formatDelta(custodyDeltas.blocked_checkpoint_delta)}`)
    }
    if (
      typeof custodyDeltas.resume_ready_delta === 'number' &&
      custodyDeltas.resume_ready_delta !== 0
    ) {
      details.push(`Resume-ready delta: ${formatDelta(custodyDeltas.resume_ready_delta)}`)
    }
  }
  return details
}

const summariseRecovery = (recovery: Record<string, any> | null | undefined): string | null => {
  if (!recovery || typeof recovery !== 'object') {
    return null
  }
  if (typeof recovery.status === 'string' && recovery.status.length > 0) {
    return `Recovery: ${recovery.status}`
  }
  if (typeof recovery.state === 'string' && recovery.state.length > 0) {
    return `Recovery: ${recovery.state}`
  }
  if (typeof recovery.pending === 'number') {
    return `Recovery pending: ${recovery.pending}`
  }
  return null
}

const collectRecoveryBundleDetails = (
  bundle: CloningPlannerRecoveryBundle | null | undefined,
): string[] => {
  if (!bundle) {
    return []
  }
  const details: string[] = []
  if (bundle.resume_ready === false) {
    details.push('Resume blocked until guardrail clears')
  } else if (bundle.resume_ready) {
    details.push('Checkpoint resume ready')
  }
  if (Array.isArray(bundle.guardrail_reasons) && bundle.guardrail_reasons.length > 0) {
    details.push(`Guardrail reasons: ${bundle.guardrail_reasons.join(', ')}`)
  }
  if (typeof bundle.open_escalations === 'number' && bundle.open_escalations > 0) {
    details.push(`Open escalations: ${bundle.open_escalations}`)
  }
  if (typeof bundle.open_drill_count === 'number' && bundle.open_drill_count > 0) {
    details.push(`Active drills: ${bundle.open_drill_count}`)
  }
  if (bundle.pending_events && bundle.pending_events.length > 0) {
    details.push(`Pending drills: ${bundle.pending_events.length}`)
  }
  if (Array.isArray(bundle.drill_summaries) && bundle.drill_summaries.length > 0) {
    const unresolved = bundle.drill_summaries.filter(
      (summary) => summary && (summary.status === 'open' || summary.resume_ready === false),
    )
    const openLabel = unresolved.length > 0 ? ` (${unresolved.length} open)` : ''
    details.push(`Drill overlays: ${bundle.drill_summaries.length}${openLabel}`)
    const severities = Array.from(
      new Set(
        bundle.drill_summaries
          .map((summary) => summary?.max_severity)
          .filter((severity): severity is string => typeof severity === 'string' && severity.length > 0),
      ),
    )
    if (severities.length > 0) {
      details.push(`Custody severity: ${severities.map((entry) => entry.toUpperCase()).join(', ')}`)
    }
  }
  if (bundle.holds && bundle.holds.length > 0) {
    details.push(`Historical holds: ${bundle.holds.length}`)
  }
  return details
}

const appendCustodySummary = (
  summary: CloningPlannerCheckpointCustodySummary | null | undefined,
  details: string[],
) => {
  if (!summary) {
    return
  }
  if (summary.max_severity) {
    details.push(`Custody severity: ${summary.max_severity.toUpperCase()}`)
  }
  if (typeof summary.open_escalations === 'number' && summary.open_escalations > 0) {
    details.push(`Custody escalations: ${summary.open_escalations}`)
  }
  if (typeof summary.open_drill_count === 'number' && summary.open_drill_count > 0) {
    details.push(`Custody drills: ${summary.open_drill_count}`)
  }
  if (typeof summary.pending_event_count === 'number' && summary.pending_event_count > 0) {
    details.push(`Custody pending drills: ${summary.pending_event_count}`)
  }
  if (summary.resume_ready === false) {
    details.push('Custody preventing resume')
  }
}

export const PlannerTimeline: React.FC<PlannerTimelineProps> = ({
  events,
  stageHistory,
  activeBranchId,
  replayWindow,
  comparisonWindow,
  mitigationHints = [],
  recoveryBundle: activeRecoveryBundle,
  onResume,
  resumePending,
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
      const branchLineage =
        (event.branch_lineage_delta as CloningPlannerBranchLineageDelta | undefined) ??
        (record?.branch_lineage as CloningPlannerBranchLineageDelta | undefined) ??
        null
      const branchComparison =
        (event.branch_comparison as CloningPlannerBranchComparison | undefined) ?? null
      const mitigationCandidates = [
        ...((event.mitigation_hints as CloningPlannerMitigationHint[] | undefined) ?? []),
        ...((record?.mitigation_hints as CloningPlannerMitigationHint[] | undefined) ?? []),
      ]
      const mitigationMap = new Map<string, CloningPlannerMitigationHint>()
      mitigationCandidates.forEach((hint) => {
        if (!hint) {
          return
        }
        const key = `${hint.category}:${hint.action}`
        if (!mitigationMap.has(key)) {
          mitigationMap.set(key, hint)
        }
      })
      const mitigation = Array.from(mitigationMap.values())
      const resumeToken =
        (event.resume_token as CloningPlannerResumeToken | undefined) ??
        (record?.resume_token as CloningPlannerResumeToken | undefined) ??
        null
      const recoveryContext =
        (event.recovery_context as Record<string, any> | undefined) ??
        (record?.recovery_context as Record<string, any> | undefined) ??
        null
      const recoveryBundle =
        (event.recovery_bundle as CloningPlannerRecoveryBundle | undefined) ??
        (record?.recovery_bundle as CloningPlannerRecoveryBundle | undefined) ??
        null
      const custodySummary =
        (record?.custody_summary as CloningPlannerCheckpointCustodySummary | undefined) ?? null
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
      const recoverySummary = summariseRecovery(recoveryContext)
      if (recoverySummary) {
        details.push(recoverySummary)
      }
      appendCustodySummary(custodySummary, details)
      collectRecoveryBundleDetails(recoveryBundle).forEach((detail) => {
        if (!details.includes(detail)) {
          details.push(detail)
        }
      })
      collectComparisonDetails(branchComparison).forEach((detail) => {
        if (detail && !details.includes(detail)) {
          details.push(detail)
        }
      })
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
        branchLineage,
        branchComparison,
        mitigationHints: mitigation,
        resumeToken,
        recoveryContext,
        recoveryBundle,
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
      const branchLineage =
        (record.branch_lineage as CloningPlannerBranchLineageDelta | undefined) ?? null
      const mitigation =
        (record.mitigation_hints as CloningPlannerMitigationHint[] | undefined) ?? []
      const recoveryContext =
        (record.recovery_context as Record<string, any> | undefined) ?? null
      const recoveryBundle =
        (record.recovery_bundle as CloningPlannerRecoveryBundle | undefined) ?? null
      const custodySummary =
        (record.custody_summary as CloningPlannerCheckpointCustodySummary | undefined) ?? null
      const recoverySummary = summariseRecovery(recoveryContext)
      if (recoverySummary) {
        details.push(recoverySummary)
      }
      appendCustodySummary(custodySummary, details)
      collectRecoveryBundleDetails(recoveryBundle).forEach((detail) => {
        if (!details.includes(detail)) {
          details.push(detail)
        }
      })
      timelineEntries.push({
        cursor,
        label: record.checkpoint_key ?? record.stage,
        timestamp: record.updated_at ?? record.completed_at ?? record.created_at ?? new Date().toISOString(),
        type: record.status,
        stage: record.stage,
        branchId: record.branch_id ?? activeBranchId ?? null,
        guardrailActive,
        details,
        branchLineage,
        branchComparison: null,
        mitigationHints: mitigation,
        resumeToken: (record.resume_token as CloningPlannerResumeToken | undefined) ?? null,
        recoveryContext,
        recoveryBundle,
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
  const replayCount = replayWindow?.length ?? timeline.length
  const comparisonCount = comparisonWindow?.length ?? 0

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

      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500" data-testid="planner-timeline-replay-summary">
        <span>Replay checkpoints: {replayCount}</span>
        {comparisonCount > 0 && <span>Comparison backlog: {comparisonCount}</span>}
      </div>

      {activeRecoveryBundle && (
        <div
          className="rounded border border-indigo-200 bg-indigo-50 p-3 text-xs text-indigo-800"
          data-testid="planner-timeline-recovery-bundle"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold">Checkpoint recovery</p>
            <span
              className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${
                activeRecoveryBundle.resume_ready === false
                  ? 'bg-amber-100 text-amber-700'
                  : 'bg-emerald-100 text-emerald-700'
              }`}
            >
              {activeRecoveryBundle.resume_ready === false ? 'Guardrail hold' : 'Resume ready'}
            </span>
          </div>
          <p className="mt-1">
            Recommended stage:{' '}
            {activeRecoveryBundle.recommended_stage ?? activeRecoveryBundle.stage ?? 'Not specified'}
          </p>
          <div className="mt-2 flex flex-wrap gap-2">
            {Array.isArray(activeRecoveryBundle.guardrail_reasons) &&
              activeRecoveryBundle.guardrail_reasons.length > 0 && (
                <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-[11px] font-semibold">
                  Reasons: {activeRecoveryBundle.guardrail_reasons.join(', ')}
                </span>
              )}
            {typeof activeRecoveryBundle.open_escalations === 'number' &&
              activeRecoveryBundle.open_escalations > 0 && (
                <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-[11px] font-semibold">
                  Open escalations: {activeRecoveryBundle.open_escalations}
                </span>
              )}
            {typeof activeRecoveryBundle.open_drill_count === 'number' &&
              activeRecoveryBundle.open_drill_count > 0 && (
                <span className="rounded-full bg-indigo-100 px-2 py-0.5 text-[11px] font-semibold">
                  Active drills: {activeRecoveryBundle.open_drill_count}
                </span>
              )}
          </div>
          {(activeRecoveryBundle.pending_events?.length ?? 0) > 0 && (
            <div className="mt-2">
              <p className="font-semibold">Pending drills</p>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {activeRecoveryBundle.pending_events?.map((event, pendingIndex) => (
                  <li key={event.event_id ?? `pending-${pendingIndex}`}>
                    {event.event_id ?? 'drill'} – open escalations: {(event.open_escalations ?? []).length}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {(activeRecoveryBundle.drill_summaries?.length ?? 0) > 0 && (
            <div className="mt-2">
              <p className="font-semibold">Custody drills</p>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {activeRecoveryBundle.drill_summaries?.map((summary, summaryIndex) => {
                  const openEscalations = summary.open_escalations?.length ?? 0
                  const severityLabel = summary.max_severity ? ` · severity: ${summary.max_severity}` : ''
                  const statusLabel = summary.status ? ` (${summary.status})` : ''
                  const readiness = summary.resume_ready === false ? ' – resume blocked' : ''
                  return (
                    <li key={summary.event_id ?? `drill-${summaryIndex}`}>
                      {summary.event_id ?? 'drill'}
                      {statusLabel}
                      {severityLabel}
                      {openEscalations > 0 ? ` · open escalations: ${openEscalations}` : ''}
                      {readiness}
                    </li>
                  )
                })}
              </ul>
            </div>
          )}
          {(activeRecoveryBundle.holds?.length ?? 0) > 0 && (
            <div className="mt-2">
              <p className="font-semibold">Recent holds</p>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {activeRecoveryBundle.holds?.map((hold, holdIndex) => (
                  <li key={`${hold.stage}-${hold.hold_started_at ?? holdIndex}`}>
                    {hold.stage} – {hold.status}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {mitigationHints.length > 0 && (
        <div
          className="rounded border border-amber-200 bg-amber-50 p-3"
          data-testid="planner-timeline-mitigations"
        >
          <p className="text-xs font-semibold text-amber-700">Active mitigation hints</p>
          <ul className="mt-2 space-y-1 text-xs text-amber-700">
            {mitigationHints.map((hint) => {
              const link = resolveHintLink(hint)
              const pending =
                typeof hint.pending === 'number'
                  ? ` (${hint.pending} pending)`
                  : ''
              const notes =
                typeof hint.notes === 'string' && hint.notes.length > 0
                  ? ` – ${hint.notes}`
                  : ''
              return (
                <li key={`${hint.category}:${hint.action}`}>
                  {link ? (
                    <a
                      href={link}
                      target="_blank"
                      rel="noreferrer"
                      className="underline"
                    >
                      Resolve {hint.action}
                    </a>
                  ) : (
                    <>Resolve {hint.action}</>
                  )}
                  {pending}
                  {notes}
                </li>
              )
            })}
          </ul>
        </div>
      )}

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
          const resumeToken = entry.resumeToken ?? null
          const comparisonDelta = formatComparisonDelta(entry.branchComparison)
          const resumeBlocked = entry.recoveryBundle?.resume_ready === false
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
              <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
                {entry.branchLineage?.branch_label && (
                  <span className="rounded-full bg-slate-100 px-2 py-0.5">
                    Lineage: {entry.branchLineage.branch_label}
                  </span>
                )}
                {typeof entry.branchLineage?.history_length === 'number' && (
                  <span className="rounded-full bg-slate-100 px-2 py-0.5">
                    Checkpoints: {entry.branchLineage.history_length}
                  </span>
                )}
                {comparisonDelta && (
                  <span className="rounded-full bg-slate-100 px-2 py-0.5">{comparisonDelta}</span>
                )}
              </div>
              {entry.details.length > 0 && (
                <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-slate-600">
                  {entry.details.map((detail) => (
                    <li key={detail}>{detail}</li>
                  ))}
                </ul>
              )}
              {entry.mitigationHints.length > 0 && (
                <div
                  className="mt-3 rounded border border-amber-100 bg-amber-50 p-2"
                  data-testid={`planner-timeline-entry-${index}-mitigations`}
                >
                  <p className="text-xs font-semibold text-amber-700">Mitigation</p>
                  <ul className="mt-1 space-y-1 text-xs text-amber-700">
                    {entry.mitigationHints.map((hint) => {
                      const link = resolveHintLink(hint)
                      const pending =
                        typeof hint.pending === 'number'
                          ? ` (${hint.pending} pending)`
                          : ''
                      return (
                        <li key={`${hint.category}:${hint.action}`}>
                          {link ? (
                            <a
                              href={link}
                              target="_blank"
                              rel="noreferrer"
                              className="underline"
                            >
                              Resolve {hint.action}
                            </a>
                          ) : (
                            <>Resolve {hint.action}</>
                          )}
                          {pending}
                        </li>
                      )
                    })}
                  </ul>
                </div>
              )}
              <div className="mt-3 flex flex-wrap gap-3">
                <button
                  type="button"
                  className="text-xs font-semibold text-slate-600 underline"
                  onClick={() => setSelectedIndex(index)}
                  aria-label={`Select timeline event ${index + 1}`}
                >
                  Scrub to event
                </button>
                {resumeToken && onResume && (
                  <button
                    type="button"
                    className="text-xs font-semibold text-slate-600 underline"
                    onClick={() => {
                      if (resumeToken) {
                        onResume(resumeToken)
                      }
                    }}
                    disabled={resumePending || resumeBlocked}
                    aria-label={`Resume from checkpoint ${entry.label}`}
                  >
                    Resume from checkpoint
                  </button>
                )}
              </div>
              {resumeBlocked && (
                <p className="mt-1 text-[11px] text-amber-600">
                  Resume is locked until guardrail mitigations complete.
                </p>
              )}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

