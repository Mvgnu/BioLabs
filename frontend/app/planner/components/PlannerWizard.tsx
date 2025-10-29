'use client'

// purpose: cloning planner multi-stage wizard mirroring backend orchestration
// status: experimental

import React, { useEffect, useMemo, useState } from 'react'

import { GuardrailBadge } from '../../components/guardrails/GuardrailBadge'
import { GuardrailEscalationPrompt } from '../../components/guardrails/GuardrailEscalationPrompt'
import { GuardrailQCDecisionLoop } from '../../components/guardrails/GuardrailQCDecisionLoop'
import { GuardrailReviewerHandoff } from '../../components/guardrails/GuardrailReviewerHandoff'
import type { CloningPlannerSession, CloningPlannerStageTiming } from '../../types'
import { useCloningPlanner } from '../../hooks/useCloningPlanner'
import { PlannerTimeline } from './PlannerTimeline'

const STAGES: { key: string; label: string; description: string }[] = [
  { key: 'primers', label: 'Primer design', description: 'Design primers and validate thermodynamics' },
  { key: 'restriction', label: 'Restriction analysis', description: 'Plan restriction digests and buffer contexts' },
  { key: 'assembly', label: 'Assembly planning', description: 'Simulate assembly strategies and ligation steps' },
  { key: 'qc', label: 'QC ingestion', description: 'Attach chromatograms and confirm guardrail thresholds' },
  { key: 'finalize', label: 'Finalize', description: 'Confirm guardrails and finalize planner session' },
]

const stateToBadge = (timing: CloningPlannerStageTiming | undefined, defaultLabel: string) => {
  if (!timing) return defaultLabel
  const status = timing.status ?? defaultLabel
  if (status.includes('errored')) return 'errored'
  if (status.includes('blocked')) return 'blocked'
  if (status.includes('running')) return 'running'
  if (status.includes('complete') || status.includes('finalized')) return 'complete'
  return status
}

const resolveGuardrailState = (session: CloningPlannerSession | undefined, key: string) => {
  return (session?.guardrail_state?.[key] as Record<string, any> | undefined) ?? {}
}

interface PlannerWizardProps {
  sessionId: string
}

export const PlannerWizard: React.FC<PlannerWizardProps> = ({ sessionId }) => {
  const [formError, setFormError] = useState<string | null>(null)
  const [primerTargetTm, setPrimerTargetTm] = useState('60')
  const [primerMin, setPrimerMin] = useState('80')
  const [primerMax, setPrimerMax] = useState('280')
  const [primerPreset, setPrimerPreset] = useState('auto')
  const [restrictionEnzymes, setRestrictionEnzymes] = useState('EcoRI,BamHI')
  const [assemblyPreset, setAssemblyPreset] = useState('gibson')
  const [qcSampleId, setQcSampleId] = useState('sample-1')
  const [qcSignal, setQcSignal] = useState('12.5')

  const { data: session, isLoading, events, runStage, resume, finalize, cancel, mutations } = useCloningPlanner(sessionId)

  const stageTimings = session?.stage_timings ?? {}
  const guardrailPrimer = resolveGuardrailState(session, 'primers')
  const guardrailRestriction = resolveGuardrailState(session, 'restriction')
  const guardrailAssembly = resolveGuardrailState(session, 'assembly')
  const guardrailQc = resolveGuardrailState(session, 'qc')
  const guardrailGate = (session?.guardrail_gate as Record<string, any> | undefined) ?? { active: false }
  const gateReasons = (guardrailGate.reasons as string[] | undefined) ?? []
  const backpressureActive = Boolean(guardrailGate.active)
  const custodyOverlay = session?.guardrail_state?.custody as Record<string, any> | undefined
  const custodyStatusRaw = (session?.guardrail_state?.custody_status as string | undefined) ?? 'stable'
  const custodyBadgeState = backpressureActive || custodyStatusRaw === 'halted' ? 'blocked' : custodyStatusRaw === 'alert' ? 'review' : 'ok'
  const custodyDetail = custodyOverlay?.open_escalations
    ? `${custodyOverlay.open_escalations} escalation${custodyOverlay.open_escalations === 1 ? '' : 's'} open`
    : undefined
  const toolkitState = session?.guardrail_state?.toolkit as Record<string, any> | undefined
  const custodyTags = useMemo(() => {
    if (!custodyOverlay) return [] as string[]
    const tags: string[] = []
    if (typeof custodyOverlay.open_escalations === 'number') {
      tags.push(`open_escalations:${custodyOverlay.open_escalations}`)
    }
    if (typeof custodyOverlay.open_drill_count === 'number' && custodyOverlay.open_drill_count > 0) {
      tags.push(`open_drills:${custodyOverlay.open_drill_count}`)
    }
    if (typeof custodyOverlay.team_id === 'string' && custodyOverlay.team_id) {
      tags.push(`team:${custodyOverlay.team_id}`)
    }
    if (typeof custodyOverlay.execution_id === 'string' && custodyOverlay.execution_id) {
      tags.push(`execution:${custodyOverlay.execution_id}`)
    }
    tags.push(`status:${custodyStatusRaw}`)
    return tags
  }, [custodyOverlay, custodyStatusRaw])
  const gateMessage = gateReasons.length > 0 ? gateReasons.join(', ') : 'Custody guardrail hold active'

  const primerState = (guardrailPrimer.primer_state as string | undefined) ?? 'unknown'
  const restrictionState =
    (guardrailRestriction.restriction_state as string | undefined) ?? (guardrailRestriction.state as string | undefined) ?? 'unknown'
  const assemblyState =
    (guardrailAssembly.assembly_state as string | undefined) ?? (guardrailAssembly.state as string | undefined) ?? 'unknown'
  const qcState = (guardrailQc.qc_state as string | undefined) ?? (guardrailQc.state as string | undefined) ?? 'unknown'

  const needsEscalation = useMemo(() => {
    return (
      backpressureActive ||
      [primerState, restrictionState, assemblyState, qcState].some((state) => state === 'review' || state === 'blocked')
    )
  }, [primerState, restrictionState, assemblyState, qcState, backpressureActive])

  const reviewerNotes = session?.stage_history?.find((entry) => Object.keys(entry.review_state || {}).length > 0)?.review_state

  useEffect(() => {
    if (toolkitState?.preset_id && primerPreset === 'auto') {
      setPrimerPreset(toolkitState.preset_id)
    }
  }, [toolkitState?.preset_id, primerPreset])

  const resolvedPreset = primerPreset === 'auto' ? toolkitState?.preset_id ?? undefined : primerPreset
  const restrictionBestStrategy = guardrailRestriction.best_strategy as Record<string, any> | undefined
  const restrictionStrategies = (guardrailRestriction.strategy_scores as Record<string, any>[] | undefined) ?? []
  const toolkitRecommended = (toolkitState?.recommended_use as string[] | undefined) ?? []
  const toolkitNotes = (toolkitState?.notes as string[] | undefined) ?? []
  const primerDetailParts: string[] = []
  if (typeof guardrailPrimer.primer_warnings === 'number' && guardrailPrimer.primer_warnings > 0) {
    primerDetailParts.push(`${guardrailPrimer.primer_warnings} warnings`)
  }
  if (typeof guardrailPrimer.multiplex_risk === 'string') {
    primerDetailParts.push(`Multiplex ${guardrailPrimer.multiplex_risk}`)
  }
  const primerDetail = primerDetailParts.join(' · ')

  const handlePrimerSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    try {
      setFormError(null)
      const payload = {
        payload: {
          target_tm: parseFloat(primerTargetTm),
          product_size_range: [parseInt(primerMin, 10), parseInt(primerMax, 10)],
          preset_id: resolvedPreset,
        },
      }
      await runStage('primers', payload)
    } catch (error) {
      setFormError((error as Error).message)
    }
  }

  const handleRestrictionSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    try {
      setFormError(null)
      const enzymes = restrictionEnzymes
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean)
      await runStage('restriction', { payload: { enzymes, preset_id: resolvedPreset } })
    } catch (error) {
      setFormError((error as Error).message)
    }
  }

  const handleAssemblySubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    try {
      setFormError(null)
      await runStage('assembly', { payload: { assembly_preset: assemblyPreset, preset_id: resolvedPreset } })
    } catch (error) {
      setFormError((error as Error).message)
    }
  }

  const handleQcSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    try {
      setFormError(null)
      const signalValue = parseFloat(qcSignal)
      const chromatograms = [
        {
          name: qcSampleId,
          trace: [signalValue, signalValue * 0.92, signalValue * 0.87],
        },
      ]
      await runStage('qc', { payload: { chromatograms } })
    } catch (error) {
      setFormError((error as Error).message)
    }
  }

  const handleResume = async () => {
    try {
      setFormError(null)
      await resume({})
    } catch (error) {
      setFormError((error as Error).message)
    }
  }

  const handleFinalize = async () => {
    try {
      setFormError(null)
      await finalize({ guardrail_state: session?.guardrail_state ?? {} })
    } catch (error) {
      setFormError((error as Error).message)
    }
  }

  const handleCancel = async () => {
    try {
      setFormError(null)
      await cancel({ reason: 'operator requested stop' })
    } catch (error) {
      setFormError((error as Error).message)
    }
  }

  if (isLoading) {
    return <div className="rounded border border-slate-200 bg-white p-6 shadow-sm">Loading cloning planner session…</div>
  }

  if (!session) {
    return <div className="rounded border border-rose-200 bg-rose-50 p-6 text-rose-700">Planner session not found.</div>
  }

  return (
    <div className="space-y-8" data-testid="planner-wizard">
      <section className="rounded border border-slate-200 bg-white p-6 shadow-sm">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold text-slate-900">Cloning planner</h1>
            <p className="text-sm text-slate-500">Strategy: {session.assembly_strategy}</p>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleResume}
              className="rounded-md border border-slate-300 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50"
              disabled={mutations.resume.isPending || backpressureActive}
            >
              Resume pipeline
            </button>
            <button
              type="button"
              onClick={handleFinalize}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
              disabled={mutations.finalize.isPending || backpressureActive}
            >
              Finalize
            </button>
            <button
              type="button"
              onClick={handleCancel}
              className="rounded-md border border-rose-200 px-3 py-1.5 text-xs font-semibold text-rose-600 hover:bg-rose-50 disabled:opacity-60"
              disabled={mutations.cancel.isPending}
            >
              Cancel
            </button>
          </div>
        </header>

        {backpressureActive && (
          <div
            className="mt-4 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-700"
            data-testid="planner-guardrail-gate"
          >
            Custody guardrails are holding this planner. Resolve escalations before continuing.
            <span className="mt-1 block text-xs text-amber-600">Reasons: {gateMessage}</span>
          </div>
        )}

        {formError && <p className="mt-3 rounded border border-rose-200 bg-rose-50 p-2 text-sm text-rose-700">{formError}</p>}

        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <div className="space-y-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Stage progress</h2>
            <ol className="space-y-3">
              {STAGES.map((stage) => {
                const timing = stageTimings[stage.key]
                return (
                  <li key={stage.key} className="rounded border border-slate-200 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{stage.label}</p>
                        <p className="text-xs text-slate-500">{stage.description}</p>
                      </div>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
                        {stateToBadge(timing, 'pending')}
                      </span>
                    </div>
                    {timing?.retries && timing.retries > 0 && (
                      <p className="mt-2 text-xs text-amber-600">Retries: {timing.retries}</p>
                    )}
                    {timing?.error && <p className="mt-2 text-xs text-rose-600">Last error: {timing.error}</p>}
                  </li>
                )
              })}
            </ol>
          </div>

          <div className="space-y-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Guardrail overview</h2>
            <div className="space-y-3">
              <GuardrailBadge
                label="Primer design"
                state={primerState}
                metadataTags={guardrailPrimer.metadata_tags ?? []}
                detail={primerDetail || undefined}
              />
              <GuardrailBadge
                label="Restriction"
                state={restrictionState}
                metadataTags={guardrailRestriction.metadata_tags ?? []}
                detail={
                  restrictionBestStrategy?.strategy
                    ? `Best: ${restrictionBestStrategy.strategy} ${Math.round((restrictionBestStrategy.compatibility ?? 0) * 100)}%`
                    : restrictionState === 'review'
                    ? 'Review recommended'
                    : undefined
                }
              />
              <GuardrailBadge label="Assembly" state={assemblyState} metadataTags={guardrailAssembly.metadata_tags ?? []} detail={guardrailAssembly.ligations ? `${guardrailAssembly.ligations.length} ligations` : undefined} />
              <GuardrailBadge label="QC" state={qcState} metadataTags={guardrailQc.metadata_tags ?? []} detail={guardrailQc.breaches?.length ? `${guardrailQc.breaches.length} breaches` : undefined} />
              <GuardrailBadge
                label="Custody"
                state={custodyBadgeState}
                metadataTags={custodyTags}
                detail={custodyDetail ?? (backpressureActive ? gateMessage : undefined)}
              />
            </div>
            {needsEscalation && (
              <GuardrailEscalationPrompt
                severity="review"
                message="Planner guardrails require review before finalization."
                metadata={{
                  primer_state: primerState,
                  restriction_state: restrictionState,
                  assembly_state: assemblyState,
                  qc_state: qcState,
                  custody_status: custodyStatusRaw,
                }}
              />
            )}
            <GuardrailReviewerHandoff
              reviewerName={(reviewerNotes?.reviewer_name as string | undefined) ?? null}
              reviewerEmail={(reviewerNotes?.reviewer_email as string | undefined) ?? null}
              reviewerRole={(reviewerNotes?.reviewer_role as string | undefined) ?? null}
              notes={(reviewerNotes?.notes as string | undefined) ?? session.guardrail_state?.review_notes}
              pendingSince={session.updated_at ?? session.created_at ?? null}
            />
            <div className="rounded border border-slate-200 p-3">
              <h3 className="text-sm font-semibold text-slate-800">Toolkit preset</h3>
              <p className="text-xs text-slate-500">
                {toolkitState?.preset_name || toolkitState?.preset_id || 'Auto detected'}
              </p>
              {toolkitRecommended.length > 0 && (
                <p className="mt-2 text-xs text-slate-500">Recommended use: {toolkitRecommended.join(', ')}</p>
              )}
              {toolkitNotes.length > 0 && (
                <ul className="mt-2 space-y-1 text-xs text-slate-500">
                  {toolkitNotes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              )}
            </div>
            {restrictionStrategies.length > 0 && (
              <div className="rounded border border-slate-200 p-3">
                <h3 className="text-sm font-semibold text-slate-800">Restriction strategies</h3>
                <ul className="mt-2 space-y-1 text-xs text-slate-500">
                  {restrictionStrategies.map((entry) => (
                    <li key={entry.strategy}>
                      {entry.strategy}: {Math.round((entry.compatibility ?? 0) * 100)}% – {entry.guardrail_hint}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
        <div className="mt-8">
          <PlannerTimeline
            events={events}
            stageHistory={session.stage_history}
            activeBranchId={session.active_branch_id ?? null}
          />
        </div>
      </section>

      <section className="rounded border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Stage controls</h2>
        {backpressureActive && (
          <p className="mt-2 text-sm text-amber-600" data-testid="planner-guardrail-warning">
            Stage execution is paused until custody guardrails clear the hold.
          </p>
        )}
        <div className="mt-4 grid gap-6 lg:grid-cols-2">
          <form onSubmit={handlePrimerSubmit} className="space-y-3" data-testid="primer-stage-form">
            <h3 className="text-sm font-semibold text-slate-800">Primer design</h3>
            <label className="flex flex-col text-xs text-slate-600">
              Primer preset
              <select
                value={primerPreset}
                onChange={(event) => setPrimerPreset(event.target.value)}
                className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm"
              >
                <option value="auto">Auto detect</option>
                <option value="multiplex">Multiplex</option>
                <option value="qpcr">qPCR validation</option>
                <option value="high_gc">High GC</option>
              </select>
            </label>
            <label className="flex flex-col text-xs text-slate-600">
              Target Tm (°C)
              <input
                type="number"
                value={primerTargetTm}
                onChange={(event) => setPrimerTargetTm(event.target.value)}
                className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm"
              />
            </label>
            <div className="flex gap-2">
              <label className="flex flex-1 flex-col text-xs text-slate-600">
                Product size min
                <input
                  type="number"
                  value={primerMin}
                  onChange={(event) => setPrimerMin(event.target.value)}
                  className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm"
                />
              </label>
              <label className="flex flex-1 flex-col text-xs text-slate-600">
                Product size max
                <input
                  type="number"
                  value={primerMax}
                  onChange={(event) => setPrimerMax(event.target.value)}
                  className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm"
                />
              </label>
            </div>
            <button
              type="submit"
              className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
              disabled={mutations.stage.isPending || backpressureActive}
            >
              Run primer stage
            </button>
          </form>

          <form onSubmit={handleRestrictionSubmit} className="space-y-3" data-testid="restriction-stage-form">
            <h3 className="text-sm font-semibold text-slate-800">Restriction analysis</h3>
            <label className="flex flex-col text-xs text-slate-600">
              Enzymes (comma separated)
              <input
                type="text"
                value={restrictionEnzymes}
                onChange={(event) => setRestrictionEnzymes(event.target.value)}
                className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm"
              />
            </label>
            <button
              type="submit"
              className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
              disabled={mutations.stage.isPending || backpressureActive}
            >
              Run restriction stage
            </button>
          </form>

          <form onSubmit={handleAssemblySubmit} className="space-y-3" data-testid="assembly-stage-form">
            <h3 className="text-sm font-semibold text-slate-800">Assembly planning</h3>
            <label className="flex flex-col text-xs text-slate-600">
              Assembly preset
              <select
                value={assemblyPreset}
                onChange={(event) => setAssemblyPreset(event.target.value)}
                className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm"
              >
                <option value="gibson">Gibson</option>
                <option value="golden_gate">Golden Gate</option>
                <option value="hifi">HiFi</option>
              </select>
            </label>
            <button
              type="submit"
              className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
              disabled={mutations.stage.isPending || backpressureActive}
            >
              Run assembly stage
            </button>
          </form>

          <form onSubmit={handleQcSubmit} className="space-y-3" data-testid="qc-stage-form">
            <h3 className="text-sm font-semibold text-slate-800">QC ingestion</h3>
            <label className="flex flex-col text-xs text-slate-600">
              Sample identifier
              <input
                type="text"
                value={qcSampleId}
                onChange={(event) => setQcSampleId(event.target.value)}
                className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm"
              />
            </label>
            <label className="flex flex-col text-xs text-slate-600">
              Signal to noise estimate
              <input
                type="number"
                step="0.1"
                value={qcSignal}
                onChange={(event) => setQcSignal(event.target.value)}
                className="mt-1 rounded border border-slate-300 px-2 py-1 text-sm"
              />
            </label>
            <button
              type="submit"
              className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
              disabled={mutations.stage.isPending || backpressureActive}
            >
              Run QC stage
            </button>
          </form>
        </div>
      </section>

      <section className="rounded border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">QC decision loop</h2>
        <GuardrailQCDecisionLoop
          artifacts={session.qc_artifacts}
          onAcknowledge={() => {
            void finalize({ guardrail_state: session.guardrail_state })
          }}
        />
      </section>

      <section className="rounded border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Event stream</h2>
        <p className="text-sm text-slate-500">Latest Redis-backed orchestration events.</p>
        <ul className="mt-3 space-y-2 text-xs text-slate-600" data-testid="planner-event-log">
          {events.length === 0 && <li>No events received yet.</li>}
          {events.map((event) => (
            <li key={`${event.timestamp}-${event.type}`} className="rounded border border-slate-200 bg-slate-50 p-2">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-700">{event.type}</span>
                <span>{new Date(event.timestamp).toLocaleTimeString()}</span>
              </div>
              <div className="mt-1 grid grid-cols-2 gap-2">
                <span>Status: {event.status}</span>
                <span>Step: {event.current_step ?? 'n/a'}</span>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

