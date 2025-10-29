'use client'

// purpose: orchestrate DNA viewer layout combining circular + linear renderers
// status: experimental

import React, { type FC, useMemo, useState } from 'react'

import { GuardrailBadge } from '../../components/guardrails/GuardrailBadge'
import { GuardrailEscalationPrompt } from '../../components/guardrails/GuardrailEscalationPrompt'
import { LifecycleSummaryPanel } from '../../components/lifecycle/LifecycleSummaryPanel'
import type { DNAViewerPayload, DNAViewerPlannerContext } from '../../types'
import { CircularGenome } from './CircularGenome'
import { LinearTrack } from './LinearTrack'

export interface DNAViewerSummaryProps {
  payload: DNAViewerPayload
}

export const DNAViewerSummary: FC<DNAViewerSummaryProps> = ({ payload }) => {
  const annotationsTrack = payload.tracks.find((track) => track.name === 'Annotations') ?? payload.tracks[0]
  const guardrailTrack = payload.tracks.find((track) => track.name === 'Guardrails')
  const guardrailStates = payload.guardrails
  const governance = payload.governance_context
  const [showAnalytics, setShowAnalytics] = useState(false)

  const custodyLedger = useMemo(() => governance.custody_ledger?.slice(0, 6) ?? [], [governance.custody_ledger])
  const timelineEntries = useMemo(() => governance.timeline?.slice(0, 10) ?? [], [governance.timeline])
  const openCustodyEscalations = useMemo(
    () => governance.custody_escalations?.filter((entry) => entry.status !== 'resolved') ?? [],
    [governance.custody_escalations],
  )
  const plannerContexts = useMemo(() => governance.planner_sessions ?? [], [governance.planner_sessions])
  const sopLinks = useMemo(() => governance.sop_links ?? [], [governance.sop_links])
  const mitigationPlaybooks = useMemo(() => governance.mitigation_playbooks ?? [], [governance.mitigation_playbooks])
  const toolkitRecommendations = payload.toolkit_recommendations ?? {}
  const toolkitScorecard = useMemo(
    () => (toolkitRecommendations.scorecard ?? {}) as Record<string, any>,
    [toolkitRecommendations.scorecard],
  )
  const toolkitStrategies = useMemo(() => {
    const scores = toolkitRecommendations.strategy_scores
    if (!Array.isArray(scores)) {
      return [] as Array<Record<string, any>>
    }
    return scores.slice(0, 3)
  }, [toolkitRecommendations.strategy_scores])

  const formatDateTime = (value?: string | null) => {
    if (!value) return 'N/A'
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) {
      return value
    }
    return date.toLocaleString()
  }

  const resolveEscalationSeverity = (severity?: string | null): 'info' | 'review' | 'critical' => {
    if (!severity) return 'info'
    const normalized = severity.toLowerCase()
    if (['critical', 'halted', 'high', 'severe'].includes(normalized)) {
      return 'critical'
    }
    if (['review', 'warning', 'medium', 'alert'].includes(normalized)) {
      return 'review'
    }
    return 'info'
  }

  const summariseResumeTarget = (context: DNAViewerPlannerContext) => {
    const token = context.replay_window?.resume_token as Record<string, any> | undefined
    if (token && typeof token === 'object') {
      const stage = token.stage ?? token.checkpoint ?? token.step
      if (stage) {
        return String(stage)
      }
    }
    return 'No checkpoint'
  }

  const primerState = useMemo(() => {
    const state = guardrailStates.primers?.primer_state ?? guardrailStates.primers?.state
    return state ?? 'unknown'
  }, [guardrailStates])

  const restrictionState = useMemo(() => {
    const state =
      guardrailStates.restriction?.restriction_state ?? guardrailStates.restriction?.state ?? guardrailStates.restriction?.status
    return state ?? 'unknown'
  }, [guardrailStates])

  const assemblyState = useMemo(() => {
    const state = guardrailStates.assembly?.assembly_state ?? guardrailStates.assembly?.state ?? guardrailStates.assembly?.status
    return state ?? 'unknown'
  }, [guardrailStates])

  const escalationMetadata = useMemo(() => {
    return {
      primer_state: primerState,
      restriction_state: restrictionState,
      assembly_state: assemblyState,
    }
  }, [primerState, restrictionState, assemblyState])

  const needsEscalation = useMemo(() => {
    return [primerState, restrictionState, assemblyState].some((state) => state === 'review' || state === 'blocked')
  }, [primerState, restrictionState, assemblyState])

  const primerDetail = useMemo(() => {
    const warnings = guardrailStates.primers?.primer_warnings
    if (typeof warnings === 'number' && warnings > 0) {
      return `${warnings} warnings`
    }
    const span = guardrailStates.primers?.tm_span
    if (typeof span === 'number') {
      return `ΔTm ${span.toFixed(2)}`
    }
    if (span) {
      return `ΔTm ${span}`
    }
    return undefined
  }, [guardrailStates])

  const restrictionDetail = useMemo(() => {
    const alerts = guardrailStates.restriction?.alerts
    if (Array.isArray(alerts) && alerts.length > 0) {
      return `${alerts.length} alerts`
    }
    return undefined
  }, [guardrailStates])

  const assemblyDetail = useMemo(() => {
    const ligations = guardrailStates.assembly?.ligations
    if (Array.isArray(ligations) && ligations.length > 0) {
      return `${ligations.length} ligation steps`
    }
    return undefined
  }, [guardrailStates])

  const recommendedBuffers = useMemo(() => {
    const buffers = toolkitScorecard.recommended_buffers
    if (Array.isArray(buffers)) {
      return buffers
    }
    return [] as string[]
  }, [toolkitScorecard.recommended_buffers])

  const primerWindowSummary = useMemo(() => {
    const window = toolkitScorecard.primer_window as Record<string, number | null> | undefined
    if (!window) {
      return 'N/A'
    }
    const min = typeof window.min_tm === 'number' ? window.min_tm.toFixed(1) : null
    const max = typeof window.max_tm === 'number' ? window.max_tm.toFixed(1) : null
    if (min && max) {
      return `${min}°C – ${max}°C`
    }
    if (min) {
      return `${min}°C`
    }
    if (max) {
      return `${max}°C`
    }
    return 'N/A'
  }, [toolkitScorecard.primer_window])

  const compatibilityIndex = useMemo(() => {
    const value = toolkitScorecard.compatibility_index
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value.toFixed(2)
    }
    return undefined
  }, [toolkitScorecard.compatibility_index])

  const presetLabel = useMemo(() => {
    if (toolkitScorecard.preset_name) {
      return String(toolkitScorecard.preset_name)
    }
    if (toolkitScorecard.preset_id) {
      return String(toolkitScorecard.preset_id)
    }
    return 'N/A'
  }, [toolkitScorecard.preset_name, toolkitScorecard.preset_id])

  const multiplexRisk = useMemo(() => {
    const risk = toolkitScorecard.multiplex_risk
    if (!risk) {
      return 'Unknown'
    }
    return String(risk)
  }, [toolkitScorecard.multiplex_risk])

  const codonUsageTop = useMemo(() => {
    const entries = Object.entries(payload.analytics?.codon_usage ?? {})
    return entries
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([codon, value]) => ({ codon, value }))
  }, [payload.analytics?.codon_usage])

  const thermodynamicRisk = payload.analytics?.thermodynamic_risk ?? {}
  const gcSkewValues = payload.analytics?.gc_skew ?? []

  return (
    <div className="space-y-8">
      <section className="rounded border border-slate-200 bg-white p-6 shadow-sm">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">{payload.asset.name}</h1>
            <p className="text-sm text-slate-500">
              {payload.sequence.length.toLocaleString()} bp • topology: {payload.topology}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {payload.asset.tags.map((tag) => (
              <span key={tag} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                {tag}
              </span>
            ))}
          </div>
        </header>
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <div className="flex h-80 items-center justify-center">
            <CircularGenome sequenceLength={payload.version.sequence_length} features={annotationsTrack?.features ?? []} />
          </div>
          <div className="space-y-4">
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Kinetics summary</h2>
              <dl className="mt-2 grid grid-cols-2 gap-3 text-sm text-slate-600">
                <div>
                  <dt className="font-medium text-slate-700">Enzymes</dt>
                  <dd>{payload.kinetics_summary.enzymes.join(', ') || 'N/A'}</dd>
                </div>
                <div>
                  <dt className="font-medium text-slate-700">Buffers</dt>
                  <dd>{payload.kinetics_summary.buffers.join(', ') || 'N/A'}</dd>
                </div>
                <div>
                  <dt className="font-medium text-slate-700">Ligation</dt>
                  <dd>{payload.kinetics_summary.ligation_profiles.join(', ') || 'N/A'}</dd>
                </div>
                <div>
                  <dt className="font-medium text-slate-700">Tags</dt>
                  <dd>{payload.kinetics_summary.metadata_tags.join(', ') || 'None'}</dd>
                </div>
              </dl>
            </div>
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Guardrail states</h2>
              <div className="mt-2 flex flex-col gap-3">
                <GuardrailBadge
                  label="Primer design"
                  state={primerState}
                  detail={primerDetail}
                  metadataTags={guardrailStates.primers?.metadata_tags ?? []}
                />
                <GuardrailBadge
                  label="Restriction digest"
                  state={restrictionState}
                  detail={restrictionDetail}
                  metadataTags={guardrailStates.restriction?.metadata_tags ?? []}
                />
                <GuardrailBadge
                  label="Assembly plan"
                  state={assemblyState}
                  detail={assemblyDetail}
                  metadataTags={guardrailStates.assembly?.metadata_tags ?? []}
                />
              </div>
            </div>
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Toolkit strategies</h2>
              <dl className="mt-2 grid grid-cols-2 gap-3 text-sm text-slate-600">
                <div>
                  <dt className="font-medium text-slate-700">Preset</dt>
                  <dd>{presetLabel}</dd>
                </div>
                <div>
                  <dt className="font-medium text-slate-700">Compatibility index</dt>
                  <dd>{compatibilityIndex ?? 'N/A'}</dd>
                </div>
                <div>
                  <dt className="font-medium text-slate-700">Multiplex risk</dt>
                  <dd>{multiplexRisk}</dd>
                </div>
                <div>
                  <dt className="font-medium text-slate-700">Primer window</dt>
                  <dd>{primerWindowSummary}</dd>
                </div>
              </dl>
              {recommendedBuffers.length > 0 && (
                <div className="mt-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Recommended buffers</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {recommendedBuffers.map((buffer) => (
                      <span
                        key={buffer}
                        className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600"
                      >
                        {buffer}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {toolkitStrategies.length > 0 && (
                <div className="mt-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Top strategies</p>
                  <ul className="mt-2 space-y-1 text-xs text-slate-600">
                    {toolkitStrategies.map((entry, index) => {
                      const label = entry.strategy ?? `Strategy ${index + 1}`
                      const score = typeof entry.compatibility === 'number' ? entry.compatibility.toFixed(2) : 'N/A'
                      return (
                        <li key={`${label}-${index}`} className="flex items-center justify-between">
                          <span className="font-medium text-slate-700">{label}</span>
                          <span className="font-mono text-slate-500">{score}</span>
                        </li>
                      )
                    })}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </div>
      </section>

      {needsEscalation && (
        <GuardrailEscalationPrompt
          severity="review"
          title="Guardrail review pending"
          message="Planner heuristics flagged review actions. Coordinate with governance reviewers before progressing."
          metadata={escalationMetadata}
        />
      )}

      {openCustodyEscalations.map((escalation) => {
        const metadata: Record<string, any> = {
          status: escalation.status,
          due_at: formatDateTime(escalation.due_at ?? escalation.created_at),
        }
        if (escalation.planner_session_id) {
          metadata.planner_session_id = escalation.planner_session_id
        }
        if (escalation.guardrail_flags?.length) {
          metadata.guardrail_flags = escalation.guardrail_flags.join(', ')
        }
        return (
          <GuardrailEscalationPrompt
            key={escalation.id}
            severity={resolveEscalationSeverity(escalation.severity)}
            title={`Custody escalation: ${escalation.reason}`}
            message={`Created ${formatDateTime(escalation.created_at)}`}
            metadata={metadata}
          />
        )
      })}

      <LifecycleSummaryPanel
        scope={{ dna_asset_id: payload.asset.id, dna_asset_version_id: payload.version.id }}
        title="Lifecycle context"
      />

      <section className="rounded border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Linear annotations</h2>
        <p className="text-sm text-slate-500">Feature spans with guardrail escalation badges</p>
        <div className="mt-4">
          <LinearTrack sequenceLength={payload.version.sequence_length} features={annotationsTrack?.features ?? []} />
        </div>
      </section>

      {guardrailTrack && (
        <section className="rounded border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Guardrail overlays</h2>
          <p className="text-sm text-slate-500">Aggregated guardrail metrics rendered as track features</p>
          <div className="mt-4">
            <LinearTrack sequenceLength={payload.version.sequence_length} features={guardrailTrack.features} />
          </div>
        </section>
      )}

      <section className="rounded border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Governance timeline</h2>
        <p className="text-sm text-slate-500">Guardrail, custody, and planner events unified for situational awareness</p>
        <div className="mt-4 space-y-3">
          {timelineEntries.length === 0 && (
            <p className="text-sm text-slate-500">No governance events recorded yet.</p>
          )}
          {timelineEntries.map((entry) => (
            <div key={entry.id} className="rounded border border-slate-200 p-3">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold text-slate-800">{entry.title}</p>
                  <p className="text-xs uppercase tracking-wide text-slate-500">{entry.source}</p>
                </div>
                <div className="text-xs text-slate-500">{formatDateTime(entry.timestamp)}</div>
              </div>
              {entry.severity && (
                <p className="mt-1 text-xs font-medium uppercase tracking-wide text-rose-600">Severity: {entry.severity}</p>
              )}
              {entry.details && Object.keys(entry.details).length > 0 && (
                <dl className="mt-2 grid grid-cols-2 gap-2 text-xs text-slate-600">
                  {Object.entries(entry.details).map(([key, value]) => (
                    <div key={key} className="space-y-0.5">
                      <dt className="font-semibold uppercase tracking-wide text-slate-500">{key}</dt>
                      <dd className="font-mono text-[11px] text-slate-700 break-all">
                        {typeof value === 'object' ? JSON.stringify(value) : String(value ?? '')}
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
          ))}
        </div>
      </section>

      <section className="rounded border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Custody ledger</h2>
        <p className="text-sm text-slate-500">Recent custody transfers aligned with planner branches</p>
        {custodyLedger.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">No custody ledger entries are linked to this asset yet.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">
                <tr>
                  <th className="px-3 py-2">Performed</th>
                  <th className="px-3 py-2">Action</th>
                  <th className="px-3 py-2">Compartment</th>
                  <th className="px-3 py-2">Branch</th>
                  <th className="px-3 py-2">Planner session</th>
                  <th className="px-3 py-2">Flags</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {custodyLedger.map((entry) => (
                  <tr key={entry.id} className="bg-white">
                    <td className="px-3 py-2 text-xs text-slate-600">{formatDateTime(entry.performed_at)}</td>
                    <td className="px-3 py-2 font-medium text-slate-700">{entry.custody_action}</td>
                    <td className="px-3 py-2 text-xs text-slate-600">{entry.compartment_label ?? 'Unassigned'}</td>
                    <td className="px-3 py-2 text-xs text-slate-600">{entry.branch_id ?? '—'}</td>
                    <td className="px-3 py-2 text-xs text-slate-600">{entry.planner_session_id ?? '—'}</td>
                    <td className="px-3 py-2 text-xs text-slate-600">
                      {entry.guardrail_flags.length > 0 ? entry.guardrail_flags.join(', ') : 'None'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {plannerContexts.length > 0 && (
        <section className="rounded border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Planner branch context</h2>
          <p className="text-sm text-slate-500">Active recovery hints and branch checkpoints from linked cloning planner sessions</p>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            {plannerContexts.map((context) => (
              <div key={context.session_id} className="rounded border border-slate-200 p-4">
                <h3 className="text-sm font-semibold text-slate-800">Session {context.session_id.slice(0, 8)}…</h3>
                <dl className="mt-3 space-y-2 text-xs text-slate-600">
                  <div className="flex items-center justify-between">
                    <dt className="font-semibold uppercase tracking-wide text-slate-500">Status</dt>
                    <dd className="text-slate-700">{context.status}</dd>
                  </div>
                  <div className="flex items-center justify-between">
                    <dt className="font-semibold uppercase tracking-wide text-slate-500">Guardrail gate</dt>
                    <dd className="text-slate-700">{context.guardrail_gate ?? 'n/a'}</dd>
                  </div>
                  <div className="flex items-center justify-between">
                    <dt className="font-semibold uppercase tracking-wide text-slate-500">Custody status</dt>
                    <dd className="text-slate-700">{context.custody_status ?? 'n/a'}</dd>
                  </div>
                  <div className="flex items-center justify-between">
                    <dt className="font-semibold uppercase tracking-wide text-slate-500">Active branch</dt>
                    <dd className="text-slate-700">{context.active_branch_id ?? 'n/a'}</dd>
                  </div>
                  <div className="flex items-center justify-between">
                    <dt className="font-semibold uppercase tracking-wide text-slate-500">Next checkpoint</dt>
                    <dd className="text-slate-700">{summariseResumeTarget(context)}</dd>
                  </div>
                  <div className="flex items-center justify-between">
                    <dt className="font-semibold uppercase tracking-wide text-slate-500">Updated</dt>
                    <dd className="text-slate-700">{formatDateTime(context.updated_at)}</dd>
                  </div>
                </dl>
              </div>
            ))}
          </div>
        </section>
      )}

      {(sopLinks.length > 0 || mitigationPlaybooks.length > 0) && (
        <section className="rounded border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Governance playbooks & SOPs</h2>
          <p className="text-sm text-slate-500">Reference links highlighted by guardrail events and mitigation presets</p>
          {mitigationPlaybooks.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {mitigationPlaybooks.map((playbook) => (
                <span key={playbook} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                  {playbook}
                </span>
              ))}
            </div>
          )}
          {sopLinks.length > 0 && (
            <ul className="mt-4 space-y-2 text-sm text-slate-600">
              {sopLinks.map((link) => (
                <li key={link}>
                  <a href={link} target="_blank" rel="noreferrer" className="text-sky-600 hover:underline">
                    {link}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      <section className="rounded border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Viewer analytics</h2>
            <p className="text-sm text-slate-500">Codon usage, GC skew, and thermodynamic overlays sourced from importer heuristics</p>
          </div>
          <button
            type="button"
            className="rounded border border-slate-300 px-3 py-1 text-sm font-medium text-slate-700 hover:bg-slate-100"
            onClick={() => setShowAnalytics((value) => !value)}
          >
            {showAnalytics ? 'Hide analytics overlays' : 'Show analytics overlays'}
          </button>
        </div>
        {showAnalytics && (
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <div>
              <h3 className="text-sm font-semibold text-slate-700">Top codons</h3>
              <ul className="mt-2 space-y-1 text-sm text-slate-600">
                {codonUsageTop.length === 0 && <li>No codon usage data</li>}
                {codonUsageTop.map(({ codon, value }) => (
                  <li key={codon} className="flex items-center justify-between">
                    <span className="font-mono">{codon}</span>
                    <span>{(value * 100).toFixed(2)}%</span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-700">GC skew windows</h3>
              <ul className="mt-2 space-y-1 text-sm text-slate-600">
                {gcSkewValues.length === 0 && <li>No GC skew data</li>}
                {gcSkewValues.map((value, index) => (
                  <li key={`gc-${index}`} className="flex items-center justify-between">
                    <span>Window {index + 1}</span>
                    <span>{value.toFixed(3)}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-700">Thermodynamic risk</h3>
              <dl className="mt-2 space-y-1 text-sm text-slate-600">
                <div className="flex items-center justify-between">
                  <dt className="font-medium text-slate-700">Overall</dt>
                  <dd className="capitalize">{thermodynamicRisk.overall_state ?? 'unknown'}</dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="font-medium text-slate-700">Primer ΔTm span</dt>
                  <dd>
                    {typeof thermodynamicRisk.primer_tm_span === 'number'
                      ? thermodynamicRisk.primer_tm_span.toFixed(2)
                      : thermodynamicRisk.primer_tm_span ?? 'N/A'}
                  </dd>
                </div>
                <div className="flex items-center justify-between">
                  <dt className="font-medium text-slate-700">Homopolymers</dt>
                  <dd>{Array.isArray(thermodynamicRisk.homopolymers) ? thermodynamicRisk.homopolymers.length : 0}</dd>
                </div>
              </dl>
            </div>
          </div>
        )}
      </section>

      {payload.translations.length > 0 && (
        <section className="rounded border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Translations</h2>
          <p className="text-sm text-slate-500">Frame-aligned amino acid translations for CDS annotations</p>
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            {payload.translations.map((translation) => (
              <div key={`${translation.label}-${translation.frame}`} className="rounded border border-slate-200 p-3">
                <h3 className="text-sm font-semibold text-slate-800">
                  {translation.label} • frame {translation.frame}
                </h3>
                <p className="mt-2 whitespace-pre-wrap break-words font-mono text-xs text-slate-700">
                  {translation.amino_acids}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      {payload.diff && (
        <section className="rounded border border-rose-200 bg-rose-50 p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-rose-700">Version diff</h2>
          <p className="text-sm text-rose-600">
            Comparing latest version with {payload.diff.from_version.version_index} → {payload.diff.to_version.version_index}
          </p>
          <dl className="mt-3 grid grid-cols-2 gap-4 text-sm text-rose-700">
            <div>
              <dt className="font-semibold">Substitutions</dt>
              <dd>{payload.diff.substitutions}</dd>
            </div>
            <div>
              <dt className="font-semibold">Insertions</dt>
              <dd>{payload.diff.insertions}</dd>
            </div>
            <div>
              <dt className="font-semibold">Deletions</dt>
              <dd>{payload.diff.deletions}</dd>
            </div>
            <div>
              <dt className="font-semibold">GC Δ</dt>
              <dd>{payload.diff.gc_delta.toFixed(3)}</dd>
            </div>
          </dl>
        </section>
      )}
    </div>
  )
}
