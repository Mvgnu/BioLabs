"use client"

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { Button, Card, CardBody, Input } from '../../components/ui'
import { Dialog } from '../../components/ui/Dialog'
import ScenarioSummary from './ScenarioSummary'
import {
  useCloneScenario,
  useCreateScenario,
  useDeleteScenario,
  useExperimentPreview,
  useScenarioWorkspace,
  useUpdateScenario,
} from '../../hooks/useExperimentConsole'
import type {
  ExperimentPreviewRequest,
  ExperimentPreviewResponse,
  ExperimentPreviewStageOverride,
  ExperimentScenario,
  ExperimentScenarioSnapshot,
} from '../../types'

interface PreviewModalProps {
  executionId: string
  open: boolean
  onClose: () => void
}

type StageOverrideDraft = {
  index: string
  slaHours: string
  assigneeId: string
  delegateId: string
}

type ResourceDraft = {
  inventory: string
  bookings: string
  equipment: string
}

// purpose: expose governance preview scenario workspace with persistence-aware UI
// status: pilot

const storageKey = (executionId: string) => `biolabs.preview.history.${executionId}`

const parseCsv = (value: string) =>
  value
    .split(',')
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0)

const stageDraftsFromScenario = (scenario: ExperimentScenario): StageOverrideDraft[] =>
  scenario.stage_overrides.map((override) => ({
    index: String(override.index),
    slaHours:
      override.sla_hours === null || override.sla_hours === undefined
        ? ''
        : String(override.sla_hours),
    assigneeId: override.assignee_id ?? '',
    delegateId: override.delegate_id ?? '',
  }))

const resourceDraftFromScenario = (scenario: ExperimentScenario): ResourceDraft => ({
  inventory: (scenario.resource_overrides?.inventory_item_ids ?? []).join(', '),
  bookings: (scenario.resource_overrides?.booking_ids ?? []).join(', '),
  equipment: (scenario.resource_overrides?.equipment_ids ?? []).join(', '),
})

const scenarioPreviewPayload = (
  scenario: ExperimentScenario,
): ExperimentPreviewRequest => ({
  workflow_template_snapshot_id: scenario.workflow_template_snapshot_id,
  stage_overrides: scenario.stage_overrides,
  resource_overrides: scenario.resource_overrides,
})

const buildStageOverridePayload = (
  drafts: StageOverrideDraft[],
): ExperimentPreviewStageOverride[] =>
  drafts
    .map((draft) => {
      if (!draft.index.trim()) return null
      const parsedIndex = Number.parseInt(draft.index, 10)
      if (Number.isNaN(parsedIndex)) return null
      const override: ExperimentPreviewStageOverride = {
        index: parsedIndex,
      }
      if (draft.slaHours.trim()) {
        const parsedSla = Number.parseInt(draft.slaHours, 10)
        if (!Number.isNaN(parsedSla)) {
          override.sla_hours = parsedSla
        }
      }
      if (draft.assigneeId.trim()) {
        override.assignee_id = draft.assigneeId.trim()
      }
      if (draft.delegateId.trim()) {
        override.delegate_id = draft.delegateId.trim()
      }
      return override
    })
    .filter((override): override is ExperimentPreviewStageOverride => Boolean(override))

const buildResourceOverridePayload = (
  draft: ResourceDraft,
): ExperimentPreviewRequest['resource_overrides'] => ({
  inventory_item_ids: parseCsv(draft.inventory),
  booking_ids: parseCsv(draft.bookings),
  equipment_ids: parseCsv(draft.equipment),
})

export default function PreviewModal({ executionId, open, onClose }: PreviewModalProps) {
  const workspace = useScenarioWorkspace(executionId)
  const previewMutation = useExperimentPreview(executionId)
  const createScenario = useCreateScenario(executionId)
  const updateScenario = useUpdateScenario(executionId)
  const cloneScenario = useCloneScenario(executionId)
  const deleteScenario = useDeleteScenario(executionId)

  const [history, setHistory] = useState<ExperimentPreviewResponse[]>([])
  const [selectedRun, setSelectedRun] = useState(0)
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null)
  const [formName, setFormName] = useState('')
  const [formDescription, setFormDescription] = useState('')
  const [formSnapshotId, setFormSnapshotId] = useState('')
  const [stageDrafts, setStageDrafts] = useState<StageOverrideDraft[]>([])
  const [resourceDraft, setResourceDraft] = useState<ResourceDraft>({
    inventory: '',
    bookings: '',
    equipment: '',
  })
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const preventAutoSelectRef = useRef(false)

  useEffect(() => {
    if (!open) return
    if (typeof window === 'undefined') return
    try {
      const raw = window.localStorage.getItem(storageKey(executionId))
      if (raw) {
        const parsed = JSON.parse(raw) as ExperimentPreviewResponse[]
        if (Array.isArray(parsed)) {
          setHistory(parsed)
          setSelectedRun(0)
        }
      }
    } catch (storageError) {
      console.warn('Unable to hydrate preview history', storageError)
    }
  }, [executionId, open])

  useEffect(() => {
    if (typeof window === 'undefined') return
    try {
      window.localStorage.setItem(storageKey(executionId), JSON.stringify(history))
    } catch (storageError) {
      console.warn('Unable to persist preview history', storageError)
    }
  }, [executionId, history])

  const snapshots = workspace.data?.snapshots ?? []
  const scenarios = workspace.data?.scenarios ?? []
  const defaultSnapshotId = snapshots[0]?.id ?? ''

  const selectedScenario = useMemo(
    () => scenarios.find((scenario) => scenario.id === selectedScenarioId) ?? null,
    [scenarios, selectedScenarioId],
  )

  const selectedSnapshot: ExperimentScenarioSnapshot | undefined = useMemo(
    () => snapshots.find((snapshot) => snapshot.id === formSnapshotId),
    [snapshots, formSnapshotId],
  )

  useEffect(() => {
    if (!workspace.data || !open) return
    if (selectedScenarioId) {
      const scenarioExists = workspace.data.scenarios.some(
        (scenario) => scenario.id === selectedScenarioId,
      )
      if (!scenarioExists) {
        setSelectedScenarioId(workspace.data.scenarios[0]?.id ?? null)
      }
      return
    }
    if (preventAutoSelectRef.current) {
      preventAutoSelectRef.current = false
      return
    }
    if (workspace.data.scenarios.length > 0) {
      setSelectedScenarioId(workspace.data.scenarios[0].id)
    } else if (!formSnapshotId) {
      setFormSnapshotId(defaultSnapshotId)
    }
  }, [workspace.data, open, selectedScenarioId, defaultSnapshotId, formSnapshotId])

  useEffect(() => {
    if (!open) return
    if (selectedScenario) {
      setFormName(selectedScenario.name)
      setFormDescription(selectedScenario.description ?? '')
      setFormSnapshotId(selectedScenario.workflow_template_snapshot_id)
      setStageDrafts(stageDraftsFromScenario(selectedScenario))
      setResourceDraft(resourceDraftFromScenario(selectedScenario))
      return
    }
    setFormName('')
    setFormDescription('')
    setFormSnapshotId(defaultSnapshotId)
    setStageDrafts([])
    setResourceDraft({ inventory: '', bookings: '', equipment: '' })
  }, [selectedScenario, defaultSnapshotId, open])

  const activePreview = useMemo(() => {
    if (history.length === 0) return null
    return history[Math.min(selectedRun, history.length - 1)]
  }, [history, selectedRun])

  const resetDraft = useCallback(() => {
    setFormName('')
    setFormDescription('')
    setFormSnapshotId(defaultSnapshotId)
    setStageDrafts([])
    setResourceDraft({ inventory: '', bookings: '', equipment: '' })
    setSelectedScenarioId(null)
  }, [defaultSnapshotId])

  const handleRunPreviewPayload = useCallback(
    async (payload: ExperimentPreviewRequest) => {
      try {
        setError(null)
        const result = await previewMutation.mutateAsync(payload)
        setHistory((prev) => [result, ...prev].slice(0, 5))
        setSelectedRun(0)
      } catch (requestError: any) {
        const detail =
          requestError?.response?.data?.detail ??
          requestError?.message ??
          'Unable to run preview simulation'
        setError(typeof detail === 'string' ? detail : 'Unable to run preview simulation')
      }
    },
    [previewMutation],
  )

  const handleRunDraftPreview = async () => {
    if (!formSnapshotId.trim()) {
      setError('Snapshot selection is required for preview runs')
      return
    }
    const stageOverrides = buildStageOverridePayload(stageDrafts)
    const resourceOverrides = buildResourceOverridePayload(resourceDraft)
    const payload: ExperimentPreviewRequest = {
      workflow_template_snapshot_id: formSnapshotId,
    }
    if (stageOverrides.length > 0) {
      payload.stage_overrides = stageOverrides
    }
    payload.resource_overrides = resourceOverrides
    await handleRunPreviewPayload(payload)
  }

  const handleRunScenarioPreview = async (scenario: ExperimentScenario) => {
    await handleRunPreviewPayload(scenarioPreviewPayload(scenario))
  }

  const handleSaveScenario = async () => {
    if (!formName.trim()) {
      setError('Scenario name is required')
      return
    }
    if (!formSnapshotId.trim()) {
      setError('Snapshot selection is required to persist a scenario')
      return
    }

    const payload = {
      name: formName.trim(),
      description: formDescription.trim() || undefined,
      workflow_template_snapshot_id: formSnapshotId,
      stage_overrides: buildStageOverridePayload(stageDrafts),
      resource_overrides: buildResourceOverridePayload(resourceDraft),
    }

    try {
      setError(null)
      setSuccessMessage(null)
      if (selectedScenario) {
        const updatedScenario = await updateScenario.mutateAsync({
          scenarioId: selectedScenario.id,
          payload,
        })
        setSuccessMessage('Scenario updated')
        setSelectedScenarioId(updatedScenario.id)
      } else {
        const createdScenario = await createScenario.mutateAsync(payload)
        setSuccessMessage('Scenario saved')
        setSelectedScenarioId(createdScenario.id)
      }
    } catch (requestError: any) {
      const detail =
        requestError?.response?.data?.detail ??
        requestError?.message ??
        'Unable to persist scenario'
      setError(typeof detail === 'string' ? detail : 'Unable to persist scenario')
    }
  }

  const handleCloneScenario = async () => {
    if (!selectedScenario) return
    try {
      setError(null)
      setSuccessMessage(null)
      const clone = await cloneScenario.mutateAsync({
        scenarioId: selectedScenario.id,
        payload: { name: `${selectedScenario.name} Copy` },
      })
      setSelectedScenarioId(clone.id)
      setSuccessMessage('Scenario cloned')
    } catch (requestError: any) {
      const detail =
        requestError?.response?.data?.detail ??
        requestError?.message ??
        'Unable to clone scenario'
      setError(typeof detail === 'string' ? detail : 'Unable to clone scenario')
    }
  }

  const handleDeleteScenario = async () => {
    if (!selectedScenario) return
    try {
      setError(null)
      setSuccessMessage(null)
      await deleteScenario.mutateAsync(selectedScenario.id)
      preventAutoSelectRef.current = true
      resetDraft()
      setSuccessMessage('Scenario deleted')
    } catch (requestError: any) {
      const detail =
        requestError?.response?.data?.detail ??
        requestError?.message ??
        'Unable to delete scenario'
      setError(typeof detail === 'string' ? detail : 'Unable to delete scenario')
    }
  }

  const handleSelectScenario = (scenario: ExperimentScenario) => {
    setSelectedScenarioId(scenario.id)
  }

  const handleNewScenario = () => {
    preventAutoSelectRef.current = true
    setSuccessMessage(null)
    resetDraft()
  }

  const handleStageDraftChange = (index: number, field: keyof StageOverrideDraft, value: string) => {
    setStageDrafts((prev) => {
      const next = [...prev]
      next[index] = { ...next[index], [field]: value }
      return next
    })
  }

  const handleRemoveStageDraft = (index: number) => {
    setStageDrafts((prev) => prev.filter((_, draftIndex) => draftIndex !== index))
  }

  const addStageDraft = () => {
    setStageDrafts((prev) => [
      ...prev,
      { index: '', slaHours: '', assigneeId: '', delegateId: '' },
    ])
  }

  const isWorkspaceLoading = workspace.isLoading && !workspace.data
  const isScenarioMutationPending =
    createScenario.isPending || updateScenario.isPending || cloneScenario.isPending || deleteScenario.isPending

  const closeModal = () => {
    setError(null)
    setSuccessMessage(null)
    previewMutation.reset()
    onClose()
  }

  return (
    <Dialog open={open} onClose={closeModal} title="Governance Preview">
      <div className="space-y-4">
        {(error || successMessage) && (
          <div>
            {error && <p className="text-sm text-rose-600">{error}</p>}
            {successMessage && <p className="text-sm text-emerald-600">{successMessage}</p>}
          </div>
        )}

        {isWorkspaceLoading ? (
          <p className="text-sm text-neutral-600">Loading scenario workspace…</p>
        ) : workspace.isError ? (
          <p className="text-sm text-rose-600">Unable to load scenario workspace.</p>
        ) : (
          <div className="grid gap-4 md:grid-cols-[1fr,1.2fr,1.2fr]">
            <section className="space-y-3">
              <header className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-neutral-900">Snapshots</h3>
                <span className="text-xs text-neutral-500">{snapshots.length} available</span>
              </header>
              {snapshots.length === 0 ? (
                <p className="text-xs text-neutral-600">No published workflow snapshots linked to this execution.</p>
              ) : (
                <ul className="space-y-2">
                  {snapshots.map((snapshot) => {
                    const isActive = snapshot.id === formSnapshotId
                    return (
                      <li key={snapshot.id}>
                        <button
                          type="button"
                          onClick={() => setFormSnapshotId(snapshot.id)}
                          className={`w-full rounded border px-3 py-2 text-left text-xs transition ${
                            isActive
                              ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                              : 'border-neutral-200 text-neutral-700 hover:border-neutral-400'
                          }`}
                        >
                          <p className="font-medium">{snapshot.template_name ?? snapshot.template_key}</p>
                          <p className="mt-1 text-[11px] text-neutral-500">
                            v{snapshot.version} · {snapshot.status}
                          </p>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}
            </section>

            <section className="space-y-3">
              <header className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-neutral-900">Scenarios</h3>
                <div className="flex items-center gap-2">
                  <Button variant="secondary" size="sm" onClick={handleNewScenario} disabled={isScenarioMutationPending}>
                    New scenario
                  </Button>
                  {selectedScenario && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={handleCloneScenario}
                      disabled={isScenarioMutationPending}
                    >
                      Clone
                    </Button>
                  )}
                  {selectedScenario && (
                    <Button
                      variant="danger"
                      size="sm"
                      onClick={handleDeleteScenario}
                      disabled={isScenarioMutationPending}
                    >
                      Delete
                    </Button>
                  )}
                </div>
              </header>

              {scenarios.length === 0 ? (
                <p className="text-xs text-neutral-600">No saved scenarios yet. Capture a draft to store it here.</p>
              ) : (
                <ul className="space-y-2">
                  {scenarios.map((scenario) => {
                    const isSelected = scenario.id === selectedScenarioId
                    return (
                      <li key={scenario.id} className="rounded border border-neutral-200 p-3">
                        <div className="flex items-center justify-between gap-2">
                          <button
                            type="button"
                            onClick={() => handleSelectScenario(scenario)}
                            className={`text-left text-sm font-medium ${
                              isSelected ? 'text-indigo-600' : 'text-neutral-800 hover:text-indigo-600'
                            }`}
                          >
                            {scenario.name}
                          </button>
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => handleRunScenarioPreview(scenario)}
                            disabled={previewMutation.isPending}
                          >
                            Run
                          </Button>
                        </div>
                        <p className="mt-1 text-[11px] text-neutral-500">
                          Updated {new Date(scenario.updated_at).toLocaleString()}
                        </p>
                      </li>
                    )
                  })}
                </ul>
              )}

              {selectedScenario && (
                <ScenarioSummary scenario={selectedScenario} snapshot={selectedSnapshot} />
              )}
            </section>

            <section className="space-y-3">
              <h3 className="text-sm font-semibold text-neutral-900">
                {selectedScenario ? 'Edit scenario' : 'Draft a new scenario'}
              </h3>

              <label className="flex flex-col text-xs font-medium text-neutral-700">
                Scenario name
                <Input value={formName} onChange={(event) => setFormName(event.target.value)} placeholder="Scenario name" />
              </label>

              <label className="flex flex-col text-xs font-medium text-neutral-700">
                Description
                <textarea
                  value={formDescription}
                  onChange={(event) => setFormDescription(event.target.value)}
                  className="mt-1 min-h-[72px] rounded-md border border-neutral-200 px-3 py-2 text-sm text-neutral-700 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                  placeholder="Optional notes for collaborators"
                />
              </label>

              <label className="flex flex-col text-xs font-medium text-neutral-700">
                Snapshot
                <select
                  className="mt-1 rounded-md border border-neutral-200 px-3 py-2 text-sm text-neutral-700 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
                  value={formSnapshotId}
                  onChange={(event) => setFormSnapshotId(event.target.value)}
                >
                  <option value="" disabled>
                    Select snapshot
                  </option>
                  {snapshots.map((snapshot) => (
                    <option key={snapshot.id} value={snapshot.id}>
                      {snapshot.template_name ?? snapshot.template_key} · v{snapshot.version}
                    </option>
                  ))}
                </select>
              </label>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-semibold text-neutral-700">Stage overrides</h4>
                  <Button size="sm" variant="ghost" onClick={addStageDraft} disabled={isScenarioMutationPending}>
                    Add stage
                  </Button>
                </div>
                {stageDrafts.length === 0 ? (
                  <p className="text-xs text-neutral-500">No stage overrides configured.</p>
                ) : (
                  <div className="space-y-2">
                    {stageDrafts.map((draft, index) => (
                      <Card key={`stage-draft-${index}`} variant="outlined">
                        <CardBody className="space-y-2">
                          <div className="grid grid-cols-2 gap-2 text-xs">
                            <label className="flex flex-col font-medium text-neutral-700">
                              Stage index
                              <Input
                                value={draft.index}
                                onChange={(event) => handleStageDraftChange(index, 'index', event.target.value)}
                                placeholder="0"
                              />
                            </label>
                            <label className="flex flex-col font-medium text-neutral-700">
                              SLA hours
                              <Input
                                value={draft.slaHours}
                                onChange={(event) => handleStageDraftChange(index, 'slaHours', event.target.value)}
                                placeholder="48"
                              />
                            </label>
                            <label className="flex flex-col font-medium text-neutral-700">
                              Assignee ID
                              <Input
                                value={draft.assigneeId}
                                onChange={(event) => handleStageDraftChange(index, 'assigneeId', event.target.value)}
                                placeholder="uuid"
                              />
                            </label>
                            <label className="flex flex-col font-medium text-neutral-700">
                              Delegate ID
                              <Input
                                value={draft.delegateId}
                                onChange={(event) => handleStageDraftChange(index, 'delegateId', event.target.value)}
                                placeholder="uuid"
                              />
                            </label>
                          </div>
                          <div className="flex justify-end">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => handleRemoveStageDraft(index)}
                              disabled={isScenarioMutationPending}
                            >
                              Remove
                            </Button>
                          </div>
                        </CardBody>
                      </Card>
                    ))}
                  </div>
                )}
              </div>

              <div className="grid grid-cols-1 gap-2 text-xs">
                <label className="flex flex-col font-medium text-neutral-700">
                  Inventory override IDs
                  <Input
                    value={resourceDraft.inventory}
                    onChange={(event) =>
                      setResourceDraft((prev) => ({ ...prev, inventory: event.target.value }))
                    }
                    placeholder="uuid, uuid"
                  />
                </label>
                <label className="flex flex-col font-medium text-neutral-700">
                  Booking override IDs
                  <Input
                    value={resourceDraft.bookings}
                    onChange={(event) =>
                      setResourceDraft((prev) => ({ ...prev, bookings: event.target.value }))
                    }
                    placeholder="uuid, uuid"
                  />
                </label>
                <label className="flex flex-col font-medium text-neutral-700">
                  Equipment override IDs
                  <Input
                    value={resourceDraft.equipment}
                    onChange={(event) =>
                      setResourceDraft((prev) => ({ ...prev, equipment: event.target.value }))
                    }
                    placeholder="uuid, uuid"
                  />
                </label>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <Button
                  onClick={handleSaveScenario}
                  loading={createScenario.isPending || updateScenario.isPending}
                  disabled={isScenarioMutationPending}
                >
                  {selectedScenario ? 'Update scenario' : 'Save scenario'}
                </Button>
                <Button
                  variant="secondary"
                  onClick={handleRunDraftPreview}
                  loading={previewMutation.isPending}
                  disabled={previewMutation.isPending}
                >
                  Run draft preview
                </Button>
              </div>
            </section>
          </div>
        )}

        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <h3 className="text-sm font-semibold text-neutral-900">Preview history</h3>
            {history.length > 1 && (
              <div className="flex items-center gap-2 text-sm">
                <span className="text-neutral-600">Compare runs:</span>
                {history.map((entry, index) => {
                  const timestamp = new Date(entry.generated_at)
                  return (
                    <button
                      key={entry.generated_at}
                      type="button"
                      onClick={() => setSelectedRun(index)}
                      className={`px-2 py-1 rounded border ${
                        index === selectedRun
                          ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                          : 'border-neutral-200 text-neutral-600 hover:border-neutral-400'
                      }`}
                    >
                      {Number.isNaN(timestamp.getTime())
                        ? `Run ${index + 1}`
                        : timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </button>
                  )
                })}
              </div>
            )}
          </div>

          {activePreview ? (
            <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
              {activePreview.resource_warnings.length > 0 && (
                <Card variant="outlined">
                  <CardBody>
                    <h4 className="text-sm font-semibold text-amber-700">Warnings</h4>
                    <ul className="mt-2 space-y-1 text-sm text-amber-700">
                      {activePreview.resource_warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  </CardBody>
                </Card>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {activePreview.stage_insights.map((stage) => {
                  const projectedDue = stage.projected_due_at ? new Date(stage.projected_due_at) : null
                  const baselineDue = stage.baseline_projected_due_at ? new Date(stage.baseline_projected_due_at) : null
                  const slaDeltaLabel =
                    typeof stage.delta_sla_hours === 'number'
                      ? `${stage.delta_sla_hours >= 0 ? '+' : ''}${stage.delta_sla_hours}h`
                      : '—'
                  const dueDeltaLabel =
                    typeof stage.delta_projected_due_minutes === 'number'
                      ? `${stage.delta_projected_due_minutes >= 0 ? '+' : ''}${stage.delta_projected_due_minutes} min`
                      : '—'
                  return (
                    <Card key={stage.index} variant="outlined">
                      <CardBody>
                        <div className="flex items-center justify-between">
                          <div>
                            <h3 className="text-sm font-semibold text-neutral-900">
                              Stage {stage.index + 1}: {stage.name || stage.required_role}
                            </h3>
                            <p className="text-xs text-neutral-500">Role: {stage.required_role}</p>
                          </div>
                          <span
                            className={`px-2 py-1 text-xs font-medium rounded ${
                              stage.status === 'ready'
                                ? 'bg-emerald-50 text-emerald-700'
                                : 'bg-rose-50 text-rose-700'
                            }`}
                          >
                            {stage.status === 'ready' ? 'Ready' : 'Blocked'}
                          </span>
                        </div>
                        <dl className="mt-3 grid grid-cols-2 gap-3 text-xs text-neutral-600">
                          <div className="space-y-1">
                            <div className="font-semibold text-neutral-700">Simulated</div>
                            <div className="flex justify-between">
                              <dt>SLA</dt>
                              <dd>{stage.sla_hours ?? '—'}</dd>
                            </div>
                            <div className="flex justify-between">
                              <dt>Projected Due</dt>
                              <dd>{projectedDue ? projectedDue.toLocaleString() : '—'}</dd>
                            </div>
                            <div className="flex justify-between">
                              <dt>Assignee</dt>
                              <dd>{stage.assignee_id ?? '—'}</dd>
                            </div>
                          </div>
                          <div className="space-y-1">
                            <div className="font-semibold text-neutral-700">Baseline</div>
                            <div className="flex justify-between">
                              <dt>SLA</dt>
                              <dd>{stage.baseline_sla_hours ?? '—'}</dd>
                            </div>
                            <div className="flex justify-between">
                              <dt>Projected Due</dt>
                              <dd>{baselineDue ? baselineDue.toLocaleString() : '—'}</dd>
                            </div>
                            <div className="flex justify-between">
                              <dt>Assignee</dt>
                              <dd>{stage.baseline_assignee_id ?? '—'}</dd>
                            </div>
                          </div>
                        </dl>
                        <dl className="mt-2 space-y-1 text-xs text-neutral-600">
                          <div className="flex justify-between">
                            <dt>Status Delta</dt>
                            <dd>{stage.delta_status ?? '—'}</dd>
                          </div>
                          <div className="flex justify-between">
                            <dt>SLA Delta</dt>
                            <dd>{slaDeltaLabel}</dd>
                          </div>
                          <div className="flex justify-between">
                            <dt>Due Delta</dt>
                            <dd>{dueDeltaLabel}</dd>
                          </div>
                        </dl>
                        {stage.blockers.length > 0 && (
                          <div className="mt-3">
                            <h4 className="text-xs font-semibold text-rose-700">Blockers</h4>
                            <ul className="mt-1 space-y-1 text-xs text-rose-700">
                              {stage.blockers.map((blocker) => (
                                <li key={blocker}>{blocker}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {(stage.delta_new_blockers.length > 0 || stage.delta_resolved_blockers.length > 0) && (
                          <div className="mt-3">
                            <h4 className="text-xs font-semibold text-indigo-700">Blocker Delta</h4>
                            {stage.delta_new_blockers.length > 0 && (
                              <div className="mt-1">
                                <p className="text-[11px] font-medium text-indigo-700">New</p>
                                <ul className="mt-1 space-y-1 text-xs text-indigo-700">
                                  {stage.delta_new_blockers.map((blocker) => (
                                    <li key={`new-${blocker}`}>{blocker}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            {stage.delta_resolved_blockers.length > 0 && (
                              <div className="mt-1">
                                <p className="text-[11px] font-medium text-emerald-700">Resolved</p>
                                <ul className="mt-1 space-y-1 text-xs text-emerald-700">
                                  {stage.delta_resolved_blockers.map((blocker) => (
                                    <li key={`resolved-${blocker}`}>{blocker}</li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        )}
                        {stage.required_actions.length > 0 && (
                          <div className="mt-3">
                            <h4 className="text-xs font-semibold text-neutral-700">Required Actions</h4>
                            <ul className="mt-1 space-y-1 text-xs text-neutral-700">
                              {stage.required_actions.map((action) => (
                                <li key={action}>{action}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {(stage.mapped_step_indexes.length > 0 || stage.gate_keys.length > 0) && (
                          <div className="mt-3 text-[11px] text-neutral-500">
                            <p>Steps: {stage.mapped_step_indexes.join(', ') || '—'}</p>
                            {stage.gate_keys.length > 0 && <p>Gate Keys: {stage.gate_keys.join(', ')}</p>}
                          </div>
                        )}
                      </CardBody>
                    </Card>
                  )
                })}
              </div>

              <Card>
                <CardBody>
                  <h3 className="text-sm font-semibold text-neutral-900">Narrative Preview</h3>
                  <pre className="mt-2 max-h-64 overflow-y-auto rounded bg-neutral-900 p-3 text-xs text-neutral-100">
                    {activePreview.narrative_preview}
                  </pre>
                </CardBody>
              </Card>
            </div>
          ) : (
            <p className="text-sm text-neutral-600">
              Configure overrides or select a scenario to generate governance ladder insights.
            </p>
          )}
        </div>
      </div>
    </Dialog>
  )
}
