'use client'

// purpose: cloning planner intake form bootstrapping new sessions
// status: experimental

import React, { useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'

import { createCloningPlannerSession } from '../api/cloningPlanner'
import { useSequenceToolkitPresets } from '../hooks/useSequenceToolkitPresets'

const PlannerIntakePage = () => {
  const router = useRouter()
  const [assemblyStrategy, setAssemblyStrategy] = useState('gibson')
  const [sequenceName, setSequenceName] = useState('vector')
  const [sequence, setSequence] = useState('ATGC'.repeat(30))
  const [metadataNotes, setMetadataNotes] = useState('Guardrail intake: primer-review')
  const [toolkitPreset, setToolkitPreset] = useState('auto')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const { data: presetCatalog } = useSequenceToolkitPresets()
  const presetOptions = useMemo(
    () => [
      { value: 'auto', label: 'Auto detect' },
      ...((presetCatalog?.presets ?? []).map((preset) => ({ value: preset.preset_id, label: preset.name }))),
    ],
    [presetCatalog?.presets],
  )
  const selectedPreset = useMemo(
    () => (presetCatalog?.presets ?? []).find((preset) => preset.preset_id === toolkitPreset) ?? null,
    [presetCatalog?.presets, toolkitPreset],
  )

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (isSubmitting) return
    setIsSubmitting(true)
    setError(null)
    try {
      const session = await createCloningPlannerSession({
        assembly_strategy: assemblyStrategy,
        input_sequences: [
          {
            name: sequenceName,
            sequence,
            metadata: { notes: metadataNotes },
          },
        ],
        metadata: {
          guardrail_state: {
            primers: { state: 'intake' },
          },
        },
        toolkit_preset: toolkitPreset === 'auto' ? null : toolkitPreset,
      })
      router.push(`/planner/${session.id}`)
    } catch (exc) {
      setError((exc as Error).message)
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6 rounded border border-slate-200 bg-white p-8 shadow-sm">
      <header>
        <h1 className="text-2xl font-semibold text-slate-900">Start a cloning planner session</h1>
        <p className="mt-2 text-sm text-slate-600">
          Provide an assembly strategy and intake sequence to bootstrap the orchestration wizard.
        </p>
      </header>
      {error && <p className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
      <form onSubmit={handleSubmit} className="space-y-4" data-testid="planner-intake-form">
        <label className="flex flex-col text-sm text-slate-700">
          Assembly strategy
          <select
            value={assemblyStrategy}
            onChange={(event) => setAssemblyStrategy(event.target.value)}
            className="mt-1 rounded border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="gibson">Gibson</option>
            <option value="golden_gate">Golden Gate</option>
            <option value="hifi">HiFi</option>
          </select>
        </label>
        <label className="flex flex-col text-sm text-slate-700">
          Sequence name
          <input
            type="text"
            value={sequenceName}
            onChange={(event) => setSequenceName(event.target.value)}
            className="mt-1 rounded border border-slate-300 px-3 py-2 text-sm"
          />
        </label>
        <label className="flex flex-col text-sm text-slate-700">
          Sequence (FASTA-like)
          <textarea
            value={sequence}
            onChange={(event) => setSequence(event.target.value)}
            rows={6}
            className="mt-1 rounded border border-slate-300 px-3 py-2 font-mono text-sm"
          />
        </label>
        <label className="flex flex-col text-sm text-slate-700">
          Intake notes
          <textarea
            value={metadataNotes}
            onChange={(event) => setMetadataNotes(event.target.value)}
            rows={3}
            className="mt-1 rounded border border-slate-300 px-3 py-2 text-sm"
          />
        </label>
        <label className="flex flex-col text-sm text-slate-700">
          Toolkit preset
          <select
            value={toolkitPreset}
            onChange={(event) => setToolkitPreset(event.target.value)}
            className="mt-1 rounded border border-slate-300 px-3 py-2 text-sm"
          >
            {presetOptions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {selectedPreset?.description && (
            <span className="mt-1 text-xs text-slate-500">{selectedPreset.description}</span>
          )}
        </label>
        <button
          type="submit"
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-60"
          disabled={isSubmitting}
        >
          Launch planner wizard
        </button>
      </form>
    </div>
  )
}

export default PlannerIntakePage

