"use client"

import { useCallback, useEffect, useMemo, useState } from 'react'

import type {
  ExperimentPreviewRequest,
  ExperimentPreviewResponse,
  GovernanceStageBlueprint,
} from '../../types'
import { useExperimentPreview } from '../../hooks/useExperimentConsole'
import { Button, Card, CardBody, Input } from '../ui'

interface LadderSimulationWidgetProps {
  stageBlueprint: GovernanceStageBlueprint[]
  defaultSla?: number | null
}

const storageKey = (executionId: string, snapshotId: string) =>
  `biolabs.ladder.simulation.${executionId}.${snapshotId}`

const parseList = (value: string) =>
  value
    .split(',')
    .map((entry) => entry.trim())
    .filter((entry) => entry.length > 0)

export default function LadderSimulationWidget({
  stageBlueprint,
  defaultSla,
}: LadderSimulationWidgetProps) {
  // purpose: allow governance authors to test ladder drafts via backend simulation preview
  // status: pilot
  const [executionId, setExecutionId] = useState('')
  const [snapshotId, setSnapshotId] = useState('')
  const [inventoryIds, setInventoryIds] = useState('')
  const [bookingIds, setBookingIds] = useState('')
  const [equipmentIds, setEquipmentIds] = useState('')
  const [history, setHistory] = useState<ExperimentPreviewResponse[]>([])
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const previewMutation = useExperimentPreview(executionId || null)

  useEffect(() => {
    if (!executionId || !snapshotId) return
    if (typeof window === 'undefined') return
    try {
      const raw = window.localStorage.getItem(storageKey(executionId, snapshotId))
      if (raw) {
        const parsed = JSON.parse(raw) as ExperimentPreviewResponse[]
        if (Array.isArray(parsed)) {
          setHistory(parsed)
          setSelectedIndex(0)
        }
      }
    } catch (storageError) {
      console.warn('Unable to hydrate ladder simulation history', storageError)
    }
  }, [executionId, snapshotId])

  useEffect(() => {
    if (!executionId || !snapshotId) return
    if (typeof window === 'undefined') return
    try {
      window.localStorage.setItem(storageKey(executionId, snapshotId), JSON.stringify(history))
    } catch (storageError) {
      console.warn('Unable to persist ladder simulation history', storageError)
    }
  }, [executionId, snapshotId, history])

  const activePreview = useMemo(() => {
    if (history.length === 0) return null
    return history[Math.min(selectedIndex, history.length - 1)]
  }, [history, selectedIndex])

  const handleSimulate = useCallback(async () => {
    if (!executionId.trim() || !snapshotId.trim()) {
      setError('Execution and snapshot identifiers are required for simulation')
      return
    }
    setError(null)
    const payload: ExperimentPreviewRequest = {
      workflow_template_snapshot_id: snapshotId.trim(),
      stage_overrides: stageBlueprint.map((stage, index) => ({
        index,
        sla_hours:
          typeof stage.sla_hours === 'number'
            ? stage.sla_hours
            : typeof defaultSla === 'number'
            ? defaultSla
            : undefined,
        assignee_id: stage.metadata?.assignee_id,
        delegate_id: stage.metadata?.delegate_id,
      })),
    }
    const resources = {
      inventory_item_ids: parseList(inventoryIds),
      booking_ids: parseList(bookingIds),
      equipment_ids: parseList(equipmentIds),
    }
    if (resources.inventory_item_ids.length || resources.booking_ids.length || resources.equipment_ids.length) {
      payload.resource_overrides = resources
    }
    try {
      const result = await previewMutation.mutateAsync(payload)
      setHistory((prev) => [result, ...prev].slice(0, 5))
      setSelectedIndex(0)
    } catch (requestError: any) {
      const detail =
        requestError?.response?.data?.detail ?? requestError?.message ?? 'Unable to simulate ladder preview'
      setError(typeof detail === 'string' ? detail : 'Unable to simulate ladder preview')
    }
  }, [
    bookingIds,
    defaultSla,
    equipmentIds,
    executionId,
    inventoryIds,
    previewMutation,
    snapshotId,
    stageBlueprint,
  ])

  return (
    <Card>
      <CardBody className="space-y-4">
        <div>
          <h3 className="text-md font-semibold text-neutral-800">Ladder simulation</h3>
          <p className="text-sm text-neutral-500">
            Preview how this draft ladder would behave for a live execution without publishing changes.
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Input
            label="Execution ID"
            value={executionId}
            onChange={(event) => setExecutionId(event.target.value)}
            placeholder="execution uuid"
          />
          <Input
            label="Snapshot ID"
            value={snapshotId}
            onChange={(event) => setSnapshotId(event.target.value)}
            placeholder="published snapshot uuid"
          />
          <Input
            label="Inventory overrides"
            value={inventoryIds}
            onChange={(event) => setInventoryIds(event.target.value)}
            placeholder="uuid, uuid"
          />
          <Input
            label="Booking overrides"
            value={bookingIds}
            onChange={(event) => setBookingIds(event.target.value)}
            placeholder="uuid, uuid"
          />
          <Input
            label="Equipment overrides"
            value={equipmentIds}
            onChange={(event) => setEquipmentIds(event.target.value)}
            placeholder="uuid, uuid"
          />
        </div>
        {error && <p className="text-sm text-rose-600">{error}</p>}
        <div className="flex items-center justify-between">
          <Button onClick={handleSimulate} disabled={previewMutation.isLoading || !executionId || !snapshotId}>
            {previewMutation.isLoading ? 'Simulating…' : 'Run simulation'}
          </Button>
          {history.length > 1 && (
            <div className="flex items-center gap-2 text-xs text-neutral-500">
              <span>Compare runs:</span>
              {history.map((entry, index) => (
                <button
                  key={entry.generated_at}
                  type="button"
                  onClick={() => setSelectedIndex(index)}
                  className={`rounded px-2 py-1 border ${
                    index === selectedIndex
                      ? 'border-indigo-500 bg-indigo-50 text-indigo-700'
                      : 'border-neutral-200 text-neutral-600 hover:border-neutral-400'
                  }`}
                >
                  {new Date(entry.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </button>
              ))}
            </div>
          )}
        </div>
        {activePreview ? (
          <div className="space-y-3">
            {activePreview.resource_warnings.length > 0 && (
              <div className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
                {activePreview.resource_warnings.join(' • ')}
              </div>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {activePreview.stage_insights.map((stage) => {
                const simulatedDue = stage.projected_due_at
                  ? new Date(stage.projected_due_at)
                  : null
                const baselineDue = stage.baseline_projected_due_at
                  ? new Date(stage.baseline_projected_due_at)
                  : null
                return (
                  <div key={stage.index} className="rounded border border-neutral-200 px-3 py-2 text-xs space-y-2">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-semibold text-neutral-800">
                          Stage {stage.index + 1}: {stage.name || stage.required_role}
                        </p>
                        <p className="text-neutral-500">Role: {stage.required_role}</p>
                      </div>
                      <span
                        className={`px-2 py-1 rounded ${
                          stage.status === 'ready'
                            ? 'bg-emerald-50 text-emerald-700'
                            : 'bg-rose-50 text-rose-700'
                        }`}
                      >
                        {stage.status === 'ready' ? 'Ready' : 'Blocked'}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-[11px] text-neutral-600">
                      <div className="space-y-1">
                        <p className="font-semibold text-neutral-700">Simulated</p>
                        <p>SLA: {stage.sla_hours ?? '—'}</p>
                        <p>Due: {simulatedDue ? simulatedDue.toLocaleString() : '—'}</p>
                        <p>Assignee: {stage.assignee_id ?? '—'}</p>
                      </div>
                      <div className="space-y-1">
                        <p className="font-semibold text-neutral-700">Baseline</p>
                        <p>SLA: {stage.baseline_sla_hours ?? '—'}</p>
                        <p>Due: {baselineDue ? baselineDue.toLocaleString() : '—'}</p>
                        <p>Assignee: {stage.baseline_assignee_id ?? '—'}</p>
                      </div>
                    </div>
                    <div className="text-[11px] text-neutral-600">
                      <p>Status delta: {stage.delta_status ?? '—'}</p>
                      <p>
                        SLA delta:{' '}
                        {typeof stage.delta_sla_hours === 'number'
                          ? `${stage.delta_sla_hours >= 0 ? '+' : ''}${stage.delta_sla_hours}h`
                          : '—'}
                      </p>
                      <p>
                        Due delta:{' '}
                        {typeof stage.delta_projected_due_minutes === 'number'
                          ? `${stage.delta_projected_due_minutes >= 0 ? '+' : ''}${stage.delta_projected_due_minutes} min`
                          : '—'}
                      </p>
                    </div>
                    {stage.blockers.length > 0 && (
                      <div className="text-rose-700">
                        <p className="font-medium">Blockers</p>
                        <ul className="list-disc pl-5 space-y-1">
                          {stage.blockers.map((blocker) => (
                            <li key={blocker}>{blocker}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {(stage.delta_new_blockers.length > 0 || stage.delta_resolved_blockers.length > 0) && (
                      <div className="space-y-2">
                        {stage.delta_new_blockers.length > 0 && (
                          <div className="text-indigo-700">
                            <p className="font-medium">New blockers</p>
                            <ul className="list-disc pl-5 space-y-1">
                              {stage.delta_new_blockers.map((blocker) => (
                                <li key={`new-${blocker}`}>{blocker}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {stage.delta_resolved_blockers.length > 0 && (
                          <div className="text-emerald-700">
                            <p className="font-medium">Resolved blockers</p>
                            <ul className="list-disc pl-5 space-y-1">
                              {stage.delta_resolved_blockers.map((blocker) => (
                                <li key={`resolved-${blocker}`}>{blocker}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        ) : (
          <p className="text-sm text-neutral-500">
            Provide an execution and snapshot identifier to preview readiness, SLA projections, and blockers for this draft.
          </p>
        )}
      </CardBody>
    </Card>
  )
}
