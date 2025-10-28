'use client'

import React, { useMemo, useState } from 'react'
import type {
  ExecutionEvent,
  ExecutionNarrativeExportCreate,
  ExecutionNarrativeExportRecord,
} from '../../../types'
import {
  useApproveNarrativeExport,
  useCreateNarrativeExport,
  useDelegateNarrativeApprovalStage,
  useExecutionNarrativeExports,
  useResetNarrativeApprovalStage,
} from '../../../hooks/useExperimentConsole'
import PreviewModal from '../PreviewModal'

const statusBadge: Record<string, string> = {
  pending: 'bg-amber-100 text-amber-700 border-amber-200',
  approved: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  rejected: 'bg-rose-100 text-rose-700 border-rose-200',
}

const stageStatusBadge: Record<string, string> = {
  pending: 'bg-neutral-50 text-neutral-600 border-neutral-200',
  in_progress: 'bg-blue-100 text-blue-700 border-blue-200',
  approved: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  rejected: 'bg-rose-100 text-rose-700 border-rose-200',
  delegated: 'bg-indigo-100 text-indigo-700 border-indigo-200',
  reset: 'bg-amber-50 text-amber-600 border-amber-200',
}

const stageStatusLabel: Record<string, string> = {
  pending: 'Pending',
  in_progress: 'In progress',
  approved: 'Approved',
  rejected: 'Rejected',
  delegated: 'Delegated',
  reset: 'Reset',
}

const artifactStatusBadge: Record<ExecutionNarrativeExportRecord['artifact_status'], string> = {
  queued: 'bg-neutral-100 text-neutral-600 border-neutral-200',
  processing: 'bg-blue-100 text-blue-700 border-blue-200',
  retrying: 'bg-amber-100 text-amber-700 border-amber-200',
  ready: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  failed: 'bg-rose-100 text-rose-700 border-rose-200',
  expired: 'bg-neutral-200 text-neutral-600 border-neutral-300',
}

const artifactStatusLabel: Record<ExecutionNarrativeExportRecord['artifact_status'], string> = {
  queued: 'Queued',
  processing: 'Packaging',
  retrying: 'Retrying',
  ready: 'Ready',
  failed: 'Failed',
  expired: 'Expired',
}

const formatDateTime = (value?: string | null) => {
  if (!value) return '—'
  try {
    return new Intl.DateTimeFormat('en', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(value))
  } catch (error) {
    return value
  }
}

const summarizeAttachment = (record: ExecutionNarrativeExportRecord) => {
  if (!record.attachments.length) return 'No attachments bundled'
  return record.attachments
    .map((attachment) => {
      if (attachment.evidence_type === 'file') {
        return attachment.file?.filename ?? 'File'
      }
      return attachment.label ?? attachment.snapshot?.event_type ?? 'Timeline event'
    })
    .join(' • ')
}

type ExportsPanelProps = {
  executionId: string
  timelineEvents: ExecutionEvent[]
}

export default function ExportsPanel({ executionId, timelineEvents }: ExportsPanelProps) {
  // purpose: orchestrate experiment narrative export creation and approval workflows
  const exportsQuery = useExecutionNarrativeExports(executionId)
  const createMutation = useCreateNarrativeExport(executionId)
  const approveMutation = useApproveNarrativeExport(executionId)
  const delegateMutation = useDelegateNarrativeApprovalStage(executionId)
  const resetStageMutation = useResetNarrativeApprovalStage(executionId)

  const [selectedEventIds, setSelectedEventIds] = useState<string[]>([])
  const [notes, setNotes] = useState('')
  const [ticket, setTicket] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [signatureInputs, setSignatureInputs] = useState<Record<string, string>>({})
  const [signatureErrors, setSignatureErrors] = useState<Record<string, string>>({})
  const [approvalNotes, setApprovalNotes] = useState<Record<string, string>>({})
  const [delegationInputs, setDelegationInputs] = useState<Record<string, string>>({})
  const [delegationDueInputs, setDelegationDueInputs] = useState<Record<string, string>>({})
  const [stageErrors, setStageErrors] = useState<Record<string, string>>({})
  const [isPreviewOpen, setPreviewOpen] = useState(false)

  const recentEvents = useMemo(() => timelineEvents.slice(0, 10), [timelineEvents])

  const toggleEventSelection = (eventId: string) => {
    setSelectedEventIds((prev) =>
      prev.includes(eventId)
        ? prev.filter((id) => id !== eventId)
        : [...prev, eventId],
    )
  }

  const resetForm = () => {
    setSelectedEventIds([])
    setNotes('')
    setTicket('')
    setFormError(null)
  }

  const handleCreate = async () => {
    setFormError(null)
    const payload: ExecutionNarrativeExportCreate = {
      notes: notes.trim() ? notes.trim() : undefined,
      metadata: ticket.trim() ? { ticket: ticket.trim() } : undefined,
      attachments: selectedEventIds.map((eventId) => ({ event_id: eventId })),
    }
    try {
      await createMutation.mutateAsync(payload)
      resetForm()
    } catch (error: any) {
      const detail =
        error?.response?.data?.detail ??
        error?.message ??
        'Unable to generate narrative export'
      setFormError(typeof detail === 'string' ? detail : 'Unable to generate narrative export')
    }
  }

  const handleApproval = async (
    record: ExecutionNarrativeExportRecord,
    stageId: string,
    status: 'approved' | 'rejected',
  ) => {
    const signature = signatureInputs[stageId]?.trim()
    if (!signature) {
      setSignatureErrors((prev) => ({ ...prev, [stageId]: 'Signature is required' }))
      return
    }
    setSignatureErrors((prev) => ({ ...prev, [stageId]: '' }))
    setStageErrors((prev) => ({ ...prev, [stageId]: '' }))
    const notes = approvalNotes[stageId]?.trim()
    try {
      await approveMutation.mutateAsync({
        exportId: record.id,
        approval: {
          status,
          signature,
          stage_id: stageId,
          notes: notes ? notes : undefined,
        },
      })
      setSignatureInputs((prev) => ({ ...prev, [stageId]: '' }))
      setApprovalNotes((prev) => ({ ...prev, [stageId]: '' }))
    } catch (error: any) {
      const detail =
        error?.response?.data?.detail ??
        error?.message ??
        'Unable to record approval'
      setStageErrors((prev) => ({
        ...prev,
        [stageId]: typeof detail === 'string' ? detail : 'Unable to record approval',
      }))
    }
  }

  const handleDelegation = async (
    record: ExecutionNarrativeExportRecord,
    stageId: string,
  ) => {
    const delegateId = delegationInputs[stageId]?.trim()
    if (!delegateId) {
      setStageErrors((prev) => ({ ...prev, [stageId]: 'Delegate user id is required' }))
      return
    }
    const rawDue = delegationDueInputs[stageId]?.trim()
    let due_at: string | undefined
    if (rawDue) {
      try {
        due_at = new Date(rawDue).toISOString()
      } catch (error) {
        setStageErrors((prev) => ({ ...prev, [stageId]: 'Invalid due date' }))
        return
      }
    }
    const notes = approvalNotes[stageId]?.trim()
    try {
      await delegateMutation.mutateAsync({
        exportId: record.id,
        stageId,
        delegation: {
          delegate_id: delegateId,
          due_at,
          notes: notes ? notes : undefined,
        },
      })
      setStageErrors((prev) => ({ ...prev, [stageId]: '' }))
      setDelegationInputs((prev) => ({ ...prev, [stageId]: '' }))
      setDelegationDueInputs((prev) => ({ ...prev, [stageId]: '' }))
    } catch (error: any) {
      const detail =
        error?.response?.data?.detail ?? error?.message ?? 'Unable to delegate stage'
      setStageErrors((prev) => ({
        ...prev,
        [stageId]: typeof detail === 'string' ? detail : 'Unable to delegate stage',
      }))
    }
  }

  const handleResetStage = async (
    record: ExecutionNarrativeExportRecord,
    stageId: string,
  ) => {
    const notes = approvalNotes[stageId]?.trim()
    try {
      await resetStageMutation.mutateAsync({
        exportId: record.id,
        stageId,
        reset: { notes: notes ? notes : undefined },
      })
      setStageErrors((prev) => ({ ...prev, [stageId]: '' }))
    } catch (error: any) {
      const detail =
        error?.response?.data?.detail ?? error?.message ?? 'Unable to reset stage'
      setStageErrors((prev) => ({
        ...prev,
        [stageId]: typeof detail === 'string' ? detail : 'Unable to reset stage',
      }))
    }
  }

  const exports = exportsQuery.data?.exports ?? []

  return (
    <section className="border border-neutral-200 rounded-lg bg-white shadow-sm p-4 space-y-6">
      <PreviewModal executionId={executionId} open={isPreviewOpen} onClose={() => setPreviewOpen(false)} />
      <header className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-xl font-semibold">Compliance Narrative Exports</h2>
          <p className="text-sm text-neutral-500">
            Generate persisted Markdown dossiers with bundled evidence and approvals.
          </p>
        </div>
        <div className="flex flex-col items-start gap-2 md:items-end">
          <button
            type="button"
            onClick={() => setPreviewOpen(true)}
            className="inline-flex items-center rounded-md border border-indigo-200 bg-indigo-50 px-3 py-1.5 text-sm font-medium text-indigo-700 hover:bg-indigo-100"
          >
            Preview Governance Impact
          </button>
          <span className="text-xs text-neutral-400">
            Execution ID: <span className="font-mono">{executionId}</span>
          </span>
        </div>
      </header>

      <div className="grid gap-4 md:grid-cols-[2fr,1fr]">
        <div className="space-y-4">
          <div className="space-y-2">
            <label className="block text-sm font-medium text-neutral-700">Export notes</label>
            <textarea
              className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows={3}
              placeholder="Summarize the compliance context for this export"
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <label className="block text-sm font-medium text-neutral-700">Ticket or reference</label>
            <input
              className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Optional tracking identifier (e.g. CAPA-1042)"
              value={ticket}
              onChange={(event) => setTicket(event.target.value)}
            />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="block text-sm font-medium text-neutral-700">Attach timeline evidence</label>
              <span className="text-xs text-neutral-400">Select up to 10 recent events</span>
            </div>
            <div className="max-h-40 overflow-y-auto rounded-md border border-neutral-200 divide-y divide-neutral-100">
              {recentEvents.length === 0 && (
                <p className="p-3 text-sm text-neutral-500">Timeline still loading…</p>
              )}
              {recentEvents.map((event) => (
                <label
                  key={event.id}
                  className="flex items-start gap-3 p-3 text-sm hover:bg-neutral-50 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={selectedEventIds.includes(event.id)}
                    onChange={() => toggleEventSelection(event.id)}
                  />
                  <div className="space-y-1">
                    <div className="font-medium text-neutral-700">{event.event_type}</div>
                    <div className="text-xs text-neutral-500">{formatDateTime(event.created_at)}</div>
                  </div>
                </label>
              ))}
            </div>
          </div>
          {formError && <p className="text-sm text-rose-600">{formError}</p>}
          <div className="flex items-center gap-3">
            <button
              type="button"
              className="inline-flex items-center justify-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-neutral-300"
              onClick={handleCreate}
              disabled={createMutation.isLoading}
            >
              {createMutation.isLoading ? 'Generating…' : 'Generate Narrative Export'}
            </button>
            <button
              type="button"
              className="text-sm text-neutral-500 hover:text-neutral-700"
              onClick={resetForm}
              disabled={createMutation.isLoading && !formError}
            >
              Reset form
            </button>
          </div>
        </div>

        <aside className="space-y-2">
          <h3 className="text-sm font-semibold text-neutral-700">Export history</h3>
          {exportsQuery.isLoading && <p className="text-sm text-neutral-500">Loading exports…</p>}
          {exportsQuery.isError && (
            <p className="text-sm text-rose-600">Unable to load narrative exports.</p>
          )}
          {exports.length === 0 && !exportsQuery.isLoading && (
            <p className="text-sm text-neutral-500">
              No exports generated yet. Create the first compliance narrative above.
            </p>
          )}
        </aside>
      </div>

      {exports.length > 0 && (
        <div className="space-y-4">
          {exports.map((record) => {
            const currentStage = record.current_stage
            const stageError = currentStage ? stageErrors[currentStage.id] : undefined
            const guardrail = record.guardrail_simulation
            const guardrailSummary = guardrail?.summary
            const guardrailState = guardrailSummary?.state ?? 'clear'
            const guardrailReasons = guardrailSummary?.reasons ?? []
            const guardrailBlockedStages = new Set<number>(
              guardrailSummary?.regressed_stage_indexes ?? [],
            )
            const guardrailProjectedDelay = guardrailSummary?.projected_delay_minutes ?? 0
            const guardrailReasonText = guardrailReasons.join(' • ')
            return (
              <article
                key={record.id}
                className="border border-neutral-200 rounded-md p-4 space-y-4 bg-neutral-50"
              >
                <header className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-neutral-700">
                        Export v{record.version}
                      </span>
                      <span
                        className={`text-xs font-medium px-2 py-1 rounded-full border ${
                          statusBadge[record.approval_status] ?? statusBadge.pending
                        }`}
                      >
                        {record.approval_status}
                      </span>
                      {guardrail && (
                        <span
                          className={`text-xs font-medium px-2 py-1 rounded-full border ${
                            guardrailState === 'blocked'
                              ? 'border-rose-200 bg-rose-50 text-rose-700'
                              : 'border-emerald-200 bg-emerald-50 text-emerald-700'
                          }`}
                          title={
                            guardrailReasonText
                              ? guardrailReasonText
                              : guardrailState === 'blocked'
                              ? 'Guardrail forecast blocking approvals'
                              : 'Guardrail forecast clear'
                          }
                        >
                          {guardrailState === 'blocked' ? 'Guardrail blocked' : 'Guardrail clear'}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-neutral-500">
                      Generated {formatDateTime(record.generated_at)} by{' '}
                      {record.requested_by.full_name ?? record.requested_by.email}
                    </p>
                  </div>
                  <div className="text-xs text-neutral-500">
                    Events: {record.event_count} • Attachments: {record.attachments.length}
                  </div>
                </header>

                {guardrailState === 'blocked' && (
                  <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                    <p className="font-medium">Forecast blocked</p>
                    {guardrailReasons.length > 0 ? (
                      <ul className="list-disc pl-4 space-y-0.5">
                        {guardrailReasons.map((reason) => (
                          <li key={reason}>{reason}</li>
                        ))}
                      </ul>
                    ) : (
                      <p>Guardrail simulations detected a blocking risk for this export.</p>
                    )}
                    {guardrailProjectedDelay > 0 && (
                      <p className="mt-1">Projected delay: {guardrailProjectedDelay} minutes</p>
                    )}
                  </div>
                )}

                {record.notes && <p className="text-sm text-neutral-700">{record.notes}</p>}

                {Object.keys(record.metadata || {}).length > 0 && (
                  <dl className="grid grid-cols-1 gap-2 text-xs text-neutral-600 md:grid-cols-2">
                    {Object.entries(record.metadata).map(([key, value]) => (
                      <div key={key}>
                        <dt className="uppercase tracking-wide text-neutral-500">{key}</dt>
                        <dd>{String(value)}</dd>
                      </div>
                    ))}
                  </dl>
                )}

                <details className="bg-white border border-neutral-200 rounded-md">
                  <summary className="cursor-pointer select-none px-3 py-2 text-sm font-medium text-neutral-700">
                    View Markdown export
                  </summary>
                  <pre className="whitespace-pre-wrap break-words p-3 text-xs text-neutral-700">
                    {record.content}
                  </pre>
                </details>

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-neutral-700">Approval ladder</h4>
                    {record.approved_by && (
                      <span className="text-xs text-neutral-500">
                        Completed {formatDateTime(record.approval_completed_at)} by{' '}
                        {record.approved_by.full_name ?? record.approved_by.email}
                      </span>
                    )}
                  </div>
                  <div className="space-y-3">
                    {record.approval_stages.map((stage) => {
                      const isCurrent = currentStage?.id === stage.id
                      const actionHistory = stage.actions.slice(-3).reverse()
                      const signatureValue = signatureInputs[stage.id] ?? ''
                      const notesValue = approvalNotes[stage.id] ?? ''
                      const delegateValue = delegationInputs[stage.id] ?? ''
                      const delegateDueValue = delegationDueInputs[stage.id] ?? ''
                      const stageIndexZero = stage.sequence_index - 1
                      const stageBlocked =
                        guardrailState === 'blocked' && guardrailBlockedStages.has(stageIndexZero)
                      const blockedTitle = stageBlocked
                        ? guardrailReasonText
                          ? `Guardrail forecast: ${guardrailReasonText}`
                          : 'Guardrail forecast blocking this stage'
                        : undefined
                      return (
                        <div
                          key={stage.id}
                          className={`rounded-md border px-3 py-3 bg-white ${
                            stageBlocked
                              ? 'border-rose-200'
                              : isCurrent
                              ? 'border-blue-200 shadow-sm'
                              : 'border-neutral-200'
                          }`}
                          title={blockedTitle}
                        >
                          <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                            <div className="space-y-1">
                              <p className="text-sm font-medium text-neutral-700">
                                Stage {stage.sequence_index}:{' '}
                                {stage.name ?? `Stage ${stage.sequence_index}`}
                              </p>
                              <p className="text-xs text-neutral-500">
                                Role: <span className="font-medium">{stage.required_role}</span>
                              </p>
                              <p className="text-xs text-neutral-500">
                                Assignee:{' '}
                                {stage.assignee?.full_name ?? stage.assignee?.email ?? 'Unassigned'}
                              </p>
                              <p className="text-xs text-neutral-500">
                                Delegate:{' '}
                                {stage.delegated_to?.full_name ?? stage.delegated_to?.email ?? 'None'}
                              </p>
                              {stage.due_at && (
                                <p className="text-xs text-neutral-500">
                                  Due {formatDateTime(stage.due_at)}
                                </p>
                              )}
                            </div>
                            <div className="flex flex-col items-end gap-1">
                              <span
                                className={`text-xs font-medium px-2 py-1 rounded-full border ${
                                  stageStatusBadge[stage.status] ?? stageStatusBadge.pending
                                }`}
                                title={blockedTitle}
                              >
                                {stageStatusLabel[stage.status] ?? stage.status}
                              </span>
                              {stage.completed_at && (
                                <span className="text-xs text-neutral-400">
                                  Completed {formatDateTime(stage.completed_at)}
                                </span>
                              )}
                            </div>
                          </div>
                          {stageBlocked && (
                            <div className="mt-2 rounded border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                              <p className="font-medium">Guardrail blocked</p>
                              {guardrailReasonText ? (
                                <p>{guardrailReasonText}</p>
                              ) : (
                                <p>Resolve forecasted risks before progressing this stage.</p>
                              )}
                              {guardrailProjectedDelay > 0 && (
                                <p className="mt-1">Projected delay: {guardrailProjectedDelay} minutes</p>
                              )}
                            </div>
                          )}
                          {actionHistory.length > 0 && (
                            <div className="mt-2 space-y-1 text-xs text-neutral-500">
                              <p className="font-medium text-neutral-600">Recent activity</p>
                              <ul className="space-y-1">
                                {actionHistory.map((action) => (
                                  <li key={action.id}>
                                    {stageStatusLabel[action.action_type] ?? action.action_type} •{' '}
                                    {action.actor.full_name ?? action.actor.email} •{' '}
                                    {formatDateTime(action.created_at)}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          )}
                          {isCurrent && (
                            <div className="mt-3 space-y-3 border-t border-neutral-200 pt-3">
                              <div className="space-y-2">
                                <label className="block text-xs font-medium text-neutral-600">
                                  Approval signature
                                </label>
                                <input
                                  className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                  placeholder="Type full name or e-signature text"
                                  value={signatureValue}
                                  onChange={(event) =>
                                    setSignatureInputs((prev) => ({
                                      ...prev,
                                      [stage.id]: event.target.value,
                                    }))
                                  }
                                  disabled={approveMutation.isLoading}
                                />
                              </div>
                              <div className="space-y-2">
                                <label className="block text-xs font-medium text-neutral-600">
                                  Stage notes (optional)
                                </label>
                                <textarea
                                  className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                  rows={2}
                                  value={notesValue}
                                  onChange={(event) =>
                                    setApprovalNotes((prev) => ({
                                      ...prev,
                                      [stage.id]: event.target.value,
                                    }))
                                  }
                                />
                              </div>
                              {stageError && (
                                <p className="text-xs text-rose-600">{stageError}</p>
                              )}
                              <div className="flex flex-wrap gap-2">
                              <button
                                type="button"
                                className="inline-flex items-center rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:bg-neutral-300"
                                onClick={() => handleApproval(record, stage.id, 'approved')}
                                disabled={approveMutation.isLoading || stageBlocked}
                                title={
                                  stageBlocked
                                    ? blockedTitle ?? 'Guardrail forecast blocking approvals'
                                    : undefined
                                }
                              >
                                Approve stage
                              </button>
                                <button
                                  type="button"
                                  className="inline-flex items-center rounded-md bg-rose-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-rose-700 disabled:bg-neutral-300"
                                  onClick={() => handleApproval(record, stage.id, 'rejected')}
                                  disabled={approveMutation.isLoading}
                                >
                                  Reject stage
                                </button>
                                <button
                                  type="button"
                                  className="inline-flex items-center rounded-md bg-neutral-200 px-3 py-1.5 text-xs font-medium text-neutral-700 hover:bg-neutral-300 disabled:bg-neutral-300"
                                  onClick={() => handleResetStage(record, stage.id)}
                                  disabled={resetStageMutation.isLoading}
                                >
                                  Reset stage
                                </button>
                              </div>
                              <div className="grid gap-2 md:grid-cols-[2fr,1fr,auto]">
                                <input
                                  className="rounded-md border border-neutral-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                  placeholder="Delegate user id"
                                  value={delegateValue}
                                  onChange={(event) =>
                                    setDelegationInputs((prev) => ({
                                      ...prev,
                                      [stage.id]: event.target.value,
                                    }))
                                  }
                                />
                                <input
                                  type="datetime-local"
                                  className="rounded-md border border-neutral-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                                  value={delegateDueValue}
                                  onChange={(event) =>
                                    setDelegationDueInputs((prev) => ({
                                      ...prev,
                                      [stage.id]: event.target.value,
                                    }))
                                  }
                                />
                              <button
                                type="button"
                                className="inline-flex items-center rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:bg-neutral-300"
                                onClick={() => handleDelegation(record, stage.id)}
                                disabled={delegateMutation.isLoading || stageBlocked}
                                title={
                                  stageBlocked
                                    ? blockedTitle ?? 'Guardrail forecast blocking delegation'
                                    : undefined
                                }
                              >
                                Delegate stage
                              </button>
                              </div>
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>

                <div className="flex flex-col gap-1 text-xs text-neutral-600">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-neutral-700">Artifact status</span>
                    <span
                      className={`px-2 py-1 rounded-full border ${artifactStatusBadge[record.artifact_status]}`}
                    >
                      {artifactStatusLabel[record.artifact_status]}
                    </span>
                    {record.artifact_status === 'ready' && record.artifact_download_path ? (
                      <a
                        href={record.artifact_download_path}
                        className="text-blue-600 hover:text-blue-700"
                      >
                        Download dossier
                      </a>
                    ) : record.artifact_status === 'failed' ? (
                      <span className="text-rose-600">
                        {record.artifact_error ?? 'Packaging failed. Generate a new export to retry.'}
                      </span>
                    ) : (
                      <span className="text-neutral-500">
                        {record.artifact_status === 'processing'
                          ? 'Packaging in progress…'
                          : 'Queued for packaging'}
                      </span>
                    )}
                  </div>
                  {record.artifact_status === 'ready' && record.artifact_checksum && (
                    <span className="font-mono text-neutral-400">
                      checksum {record.artifact_checksum.slice(0, 8)}…
                      {record.artifact_checksum.slice(-4)}
                    </span>
                  )}
                  {record.artifact_status === 'ready' && record.artifact_file?.filename && (
                    <span className="text-neutral-500">
                      File: {record.artifact_file.filename} •{' '}
                      {Math.max(
                        1,
                        Math.round((record.artifact_file?.file_size ?? 0) / 1024),
                      )}{' '}
                      KB
                    </span>
                  )}
                </div>

                <div className="text-xs text-neutral-600">
                  <p className="font-medium text-neutral-700">Bundled evidence</p>
                  <p>{summarizeAttachment(record)}</p>
                </div>
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}
