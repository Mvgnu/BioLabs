'use client'

// purpose: orchestrate DNA viewer layout combining circular + linear renderers
// status: experimental

import React, { type FC, useMemo } from 'react'

import { GuardrailBadge } from '../../components/guardrails/GuardrailBadge'
import { GuardrailEscalationPrompt } from '../../components/guardrails/GuardrailEscalationPrompt'
import type { DNAViewerPayload } from '../../types'
import { CircularGenome } from './CircularGenome'
import { LinearTrack } from './LinearTrack'

export interface DNAViewerSummaryProps {
  payload: DNAViewerPayload
}

export const DNAViewerSummary: FC<DNAViewerSummaryProps> = ({ payload }) => {
  const annotationsTrack = payload.tracks.find((track) => track.name === 'Annotations') ?? payload.tracks[0]
  const guardrailTrack = payload.tracks.find((track) => track.name === 'Guardrails')
  const guardrailStates = payload.guardrails

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
