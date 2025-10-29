'use client'

// purpose: cloning planner multi-stage wizard mirroring backend orchestration
// status: experimental

import React, { useMemo, useState } from 'react'

import { GuardrailBadge } from '../../components/guardrails/GuardrailBadge'
import { GuardrailEscalationPrompt } from '../../components/guardrails/GuardrailEscalationPrompt'
import { GuardrailQCDecisionLoop } from '../../components/guardrails/GuardrailQCDecisionLoop'
import { GuardrailReviewerHandoff } from '../../components/guardrails/GuardrailReviewerHandoff'
import type { CloningPlannerSession, CloningPlannerStageTiming } from '../../types'
import { useCloningPlanner } from '../../hooks/useCloningPlanner'

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

  const primerState = (guardrailPrimer.primer_state as string | undefined) ?? 'unknown'
  const restrictionState =
    (guardrailRestriction.restriction_state as string | undefined) ?? (guardrailRestriction.state as string | undefined) ?? 'unknown'
  const assemblyState =
    (guardrailAssembly.assembly_state as string | undefined) ?? (guardrailAssembly.state as string | undefined) ?? 'unknown'
  const qcState = (guardrailQc.qc_state as string | undefined) ?? (guardrailQc.state as string | undefined) ?? 'unknown'

  const needsEscalation = useMemo(() => {
    return [primerState, restrictionState, assemblyState, qcState].some((state) => state === 'review' || state === 'blocked')
  }, [primerState, restrictionState, assemblyState, qcState])

  const reviewerNotes = session?.stage_history?.find((entry) => Object.keys(entry.review_state || {}).length > 0)?.review_state

  const handlePrimerSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    try {
      setFormError(null)
      const payload = {
        payload: {
          target_tm: parseFloat(primerTargetTm),
          product_size_range: [parseInt(primerMin, 10), parseInt(primerMax, 10)],
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
      await runStage('restriction', { payload: { enzymes } })
    } catch (error) {
      setFormError((error as Error).message)
    }
  }

  const handleAssemblySubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    try {
      setFormError(null)
      await runStage('assembly', { payload: { assembly_preset: assemblyPreset } })
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
              disabled={mutations.resume.isPending}
            >
              Resume pipeline
            </button>
            <button
              type="button"
              onClick={handleFinalize}
              className="rounded-md bg-slate-900 px-3 py-1.5 text-xs font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
              disabled={mutations.finalize.isPending}
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
              <GuardrailBadge label="Primer design" state={primerState} metadataTags={guardrailPrimer.metadata_tags ?? []} detail={guardrailPrimer.primer_warnings ? `${guardrailPrimer.primer_warnings} warnings` : undefined} />
              <GuardrailBadge label="Restriction" state={restrictionState} metadataTags={guardrailRestriction.metadata_tags ?? []} detail={restrictionState === 'review' ? 'Review recommended' : undefined} />
              <GuardrailBadge label="Assembly" state={assemblyState} metadataTags={guardrailAssembly.metadata_tags ?? []} detail={guardrailAssembly.ligations ? `${guardrailAssembly.ligations.length} ligations` : undefined} />
              <GuardrailBadge label="QC" state={qcState} metadataTags={guardrailQc.metadata_tags ?? []} detail={guardrailQc.breaches?.length ? `${guardrailQc.breaches.length} breaches` : undefined} />
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
          </div>
        </div>
      </section>

      <section className="rounded border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="text-lg font-semibold text-slate-900">Stage controls</h2>
        <div className="mt-4 grid gap-6 lg:grid-cols-2">
          <form onSubmit={handlePrimerSubmit} className="space-y-3" data-testid="primer-stage-form">
            <h3 className="text-sm font-semibold text-slate-800">Primer design</h3>
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
              disabled={mutations.stage.isPending}
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
              disabled={mutations.stage.isPending}
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
              disabled={mutations.stage.isPending}
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
              disabled={mutations.stage.isPending}
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

