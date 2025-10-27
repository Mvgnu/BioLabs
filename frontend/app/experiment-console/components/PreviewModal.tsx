"use client"

import { useCallback, useEffect, useMemo, useState } from 'react'

import { Button, Card, CardBody, Input } from '../../components/ui'
import { Dialog } from '../../components/ui/Dialog'
import type {
  ExperimentPreviewRequest,
  ExperimentPreviewResponse,
} from '../../types'
import { useExperimentPreview } from '../../hooks/useExperimentConsole'

interface PreviewModalProps {
  executionId: string
  open: boolean
  onClose: () => void
}

// purpose: expose governance preview modal with simulation controls for experiment console
// status: pilot

const storageKey = (executionId: string) => `biolabs.preview.history.${executionId}`

const parseCsv = (value: string) =>
  value
    .split(',')
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0)

export default function PreviewModal({ executionId, open, onClose }: PreviewModalProps) {
  const previewMutation = useExperimentPreview(executionId)
  const [snapshotId, setSnapshotId] = useState('')
  const [stageIndex, setStageIndex] = useState('')
  const [slaOverride, setSlaOverride] = useState('')
  const [assigneeId, setAssigneeId] = useState('')
  const [delegateId, setDelegateId] = useState('')
  const [inventoryIds, setInventoryIds] = useState('')
  const [bookingIds, setBookingIds] = useState('')
  const [equipmentIds, setEquipmentIds] = useState('')
  const [history, setHistory] = useState<ExperimentPreviewResponse[]>([])
  const [selectedRun, setSelectedRun] = useState(0)
  const [error, setError] = useState<string | null>(null)

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

  const activePreview = useMemo(() => {
    if (history.length === 0) return null
    return history[Math.min(selectedRun, history.length - 1)]
  }, [history, selectedRun])

  const handleRunPreview = useCallback(async () => {
    if (!snapshotId.trim()) {
      setError('Snapshot identifier is required')
      return
    }
    setError(null)
    const payload: ExperimentPreviewRequest = {
      workflow_template_snapshot_id: snapshotId.trim(),
    }
    const overrides = parseInt(stageIndex, 10)
    if (!Number.isNaN(overrides)) {
      payload.stage_overrides = [
        {
          index: overrides,
          sla_hours: slaOverride ? Number.parseInt(slaOverride, 10) || undefined : undefined,
          assignee_id: assigneeId.trim() || undefined,
          delegate_id: delegateId.trim() || undefined,
        },
      ]
    }
    const resources = {
      inventory_item_ids: parseCsv(inventoryIds),
      booking_ids: parseCsv(bookingIds),
      equipment_ids: parseCsv(equipmentIds),
    }
    if (resources.inventory_item_ids.length || resources.booking_ids.length || resources.equipment_ids.length) {
      payload.resource_overrides = resources
    }
    try {
      const result = await previewMutation.mutateAsync(payload)
      setHistory((prev) => [result, ...prev].slice(0, 5))
      setSelectedRun(0)
    } catch (requestError: any) {
      const detail =
        requestError?.response?.data?.detail ?? requestError?.message ?? 'Unable to run preview simulation'
      setError(typeof detail === 'string' ? detail : 'Unable to run preview simulation')
    }
  }, [
    assigneeId,
    bookingIds,
    delegateId,
    equipmentIds,
    inventoryIds,
    previewMutation,
    slaOverride,
    snapshotId,
    stageIndex,
  ])

  const closeModal = () => {
    setError(null)
    previewMutation.reset()
    onClose()
  }

  return (
    <Dialog open={open} onClose={closeModal} title="Governance Preview">
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="flex flex-col text-sm font-medium text-neutral-700">
            Snapshot ID
            <Input
              value={snapshotId}
              onChange={(event) => setSnapshotId(event.target.value)}
              placeholder="00000000-0000-0000-0000-000000000000"
            />
          </label>
          <label className="flex flex-col text-sm font-medium text-neutral-700">
            Stage Index Override
            <Input
              value={stageIndex}
              onChange={(event) => setStageIndex(event.target.value)}
              placeholder="0"
            />
          </label>
          <label className="flex flex-col text-sm font-medium text-neutral-700">
            Override SLA Hours
            <Input
              value={slaOverride}
              onChange={(event) => setSlaOverride(event.target.value)}
              placeholder="48"
            />
          </label>
          <label className="flex flex-col text-sm font-medium text-neutral-700">
            Override Assignee ID
            <Input
              value={assigneeId}
              onChange={(event) => setAssigneeId(event.target.value)}
              placeholder="optional"
            />
          </label>
          <label className="flex flex-col text-sm font-medium text-neutral-700">
            Delegate ID
            <Input
              value={delegateId}
              onChange={(event) => setDelegateId(event.target.value)}
              placeholder="optional"
            />
          </label>
          <label className="flex flex-col text-sm font-medium text-neutral-700">
            Inventory Override IDs
            <Input
              value={inventoryIds}
              onChange={(event) => setInventoryIds(event.target.value)}
              placeholder="uuid,uuid"
            />
          </label>
          <label className="flex flex-col text-sm font-medium text-neutral-700">
            Booking Override IDs
            <Input
              value={bookingIds}
              onChange={(event) => setBookingIds(event.target.value)}
              placeholder="uuid,uuid"
            />
          </label>
          <label className="flex flex-col text-sm font-medium text-neutral-700">
            Equipment Override IDs
            <Input
              value={equipmentIds}
              onChange={(event) => setEquipmentIds(event.target.value)}
              placeholder="uuid,uuid"
            />
          </label>
        </div>

        {error && <p className="text-sm text-rose-600">{error}</p>}

        <div className="flex items-center justify-between gap-3">
          <Button onClick={handleRunPreview} disabled={previewMutation.isLoading}>
            {previewMutation.isLoading ? 'Running Preview…' : 'Run Preview'}
          </Button>
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
                const projectedDue = stage.projected_due_at
                  ? new Date(stage.projected_due_at)
                  : null
                const baselineDue = stage.baseline_projected_due_at
                  ? new Date(stage.baseline_projected_due_at)
                  : null
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
                <pre className="mt-2 max-h-64 overflow-y-auto rounded bg-neutral-900 text-neutral-100 p-3 text-xs">
                  {activePreview.narrative_preview}
                </pre>
              </CardBody>
            </Card>
          </div>
        ) : (
          <p className="text-sm text-neutral-600">
            Provide a published snapshot identifier and run a preview to see governance insights.
          </p>
        )}
      </div>
    </Dialog>
  )
}
