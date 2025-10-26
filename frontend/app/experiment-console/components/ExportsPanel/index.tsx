'use client'

import { useMemo, useState } from 'react'
import type {
  ExecutionEvent,
  ExecutionNarrativeExportCreate,
  ExecutionNarrativeExportRecord,
} from '../../../types'
import {
  useApproveNarrativeExport,
  useCreateNarrativeExport,
  useExecutionNarrativeExports,
} from '../../../hooks/useExperimentConsole'

const statusBadge: Record<string, string> = {
  pending: 'bg-amber-100 text-amber-700 border-amber-200',
  approved: 'bg-emerald-100 text-emerald-700 border-emerald-200',
  rejected: 'bg-rose-100 text-rose-700 border-rose-200',
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

  const [selectedEventIds, setSelectedEventIds] = useState<string[]>([])
  const [notes, setNotes] = useState('')
  const [ticket, setTicket] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [signatureInputs, setSignatureInputs] = useState<Record<string, string>>({})
  const [signatureErrors, setSignatureErrors] = useState<Record<string, string>>({})

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
    status: 'approved' | 'rejected',
  ) => {
    const signature = signatureInputs[record.id]?.trim()
    if (!signature) {
      setSignatureErrors((prev) => ({ ...prev, [record.id]: 'Signature is required' }))
      return
    }
    setSignatureErrors((prev) => ({ ...prev, [record.id]: '' }))
    try {
      await approveMutation.mutateAsync({
        exportId: record.id,
        approval: { status, signature },
      })
      setSignatureInputs((prev) => ({ ...prev, [record.id]: '' }))
    } catch (error: any) {
      const detail =
        error?.response?.data?.detail ??
        error?.message ??
        'Unable to record approval'
      setSignatureErrors((prev) => ({
        ...prev,
        [record.id]: typeof detail === 'string' ? detail : 'Unable to record approval',
      }))
    }
  }

  const exports = exportsQuery.data?.exports ?? []

  return (
    <section className="border border-neutral-200 rounded-lg bg-white shadow-sm p-4 space-y-6">
      <header className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-xl font-semibold">Compliance Narrative Exports</h2>
          <p className="text-sm text-neutral-500">
            Generate persisted Markdown dossiers with bundled evidence and approvals.
          </p>
        </div>
        <span className="text-xs text-neutral-400">
          Execution ID: <span className="font-mono">{executionId}</span>
        </span>
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
            const canDecide = record.approval_status === 'pending'
            return (
              <article
                key={record.id}
                className="border border-neutral-200 rounded-md p-4 space-y-3 bg-neutral-50"
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

                <div className="text-xs text-neutral-600">
                  <p className="font-medium text-neutral-700">Bundled evidence</p>
                  <p>{summarizeAttachment(record)}</p>
                </div>

                <div className="space-y-2">
                  <label className="block text-xs font-medium text-neutral-600">
                    Approval signature
                  </label>
                  <input
                    className="w-full rounded-md border border-neutral-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Type full name or e-signature text"
                    value={signatureInputs[record.id] ?? ''}
                    onChange={(event) =>
                      setSignatureInputs((prev) => ({ ...prev, [record.id]: event.target.value }))
                    }
                    disabled={!canDecide}
                  />
                  {signatureErrors[record.id] && (
                    <p className="text-xs text-rose-600">{signatureErrors[record.id]}</p>
                  )}
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      className="inline-flex items-center rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700 disabled:bg-neutral-300"
                      onClick={() => handleApproval(record, 'approved')}
                      disabled={approveMutation.isLoading || !canDecide}
                    >
                      Approve export
                    </button>
                    <button
                      type="button"
                      className="inline-flex items-center rounded-md bg-rose-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-rose-700 disabled:bg-neutral-300"
                      onClick={() => handleApproval(record, 'rejected')}
                      disabled={approveMutation.isLoading || !canDecide}
                    >
                      Reject export
                    </button>
                    {record.approval_signature && (
                      <span className="text-xs text-neutral-500">
                        Signed {formatDateTime(record.approved_at)} by{' '}
                        {record.approved_by?.full_name ?? record.approved_by?.email}
                      </span>
                    )}
                  </div>
                </div>
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}
