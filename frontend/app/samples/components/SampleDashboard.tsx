'use client'

import React from 'react'

import { GuardrailBadge } from '../../components/guardrails/GuardrailBadge'
import { useSampleSummaries, useSampleDetail } from '../../hooks/useSamples'
import type { InventorySampleSummary } from '../../types'
import Link from 'next/link'

// purpose: present custody-aware sample dashboards with guardrail context and linked records
// status: pilot

const SampleDashboard: React.FC = () => {
  const { data: summaries, isLoading, error } = useSampleSummaries()
  const [selectedSample, setSelectedSample] = React.useState<string | null>(null)
  const { data: detail, isLoading: detailLoading } = useSampleDetail(selectedSample)

  React.useEffect(() => {
    if (!selectedSample && summaries && summaries.length > 0) {
      setSelectedSample(summaries[0].id)
    }
  }, [summaries, selectedSample])

  if (isLoading) {
    return <div className="p-8 text-sm text-slate-600">Loading sample custody dashboard…</div>
  }

  if (error) {
    return (
      <div className="p-8 text-sm text-rose-600">
        Unable to load sample custody data. Please retry or contact an administrator.
      </div>
    )
  }

  if (!summaries || summaries.length === 0) {
    return (
      <div className="p-8 text-sm text-slate-600">
        No custody-linked samples were found within your team scope.
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <section className="space-y-3">
        <header className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-slate-900">Sample custody overview</h1>
            <p className="text-sm text-slate-500">
              Review custody state, guardrail flags, and escalations across governed samples.
            </p>
          </div>
        </header>
        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-4 py-2 text-left font-medium text-slate-500">Sample</th>
                <th className="px-4 py-2 text-left font-medium text-slate-500">Custody state</th>
                <th className="px-4 py-2 text-left font-medium text-slate-500">Guardrail flags</th>
                <th className="px-4 py-2 text-left font-medium text-slate-500">Open escalations</th>
                <th className="px-4 py-2 text-left font-medium text-slate-500">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {summaries.map((sample) => (
                <SampleRow
                  key={sample.id}
                  sample={sample}
                  selected={selectedSample === sample.id}
                  onSelect={() => setSelectedSample(sample.id)}
                />
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="space-y-3">
        <header className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-900">Sample detail</h2>
            <p className="text-sm text-slate-500">
              Inspect custody ledger events, guardrail escalations, and linked planner or DNA records.
            </p>
          </div>
        </header>
        {detailLoading && (
          <div className="rounded-md border border-slate-200 bg-white p-6 text-sm text-slate-600">
            Loading custody history…
          </div>
        )}
        {!detailLoading && detail && (
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="space-y-4 rounded-md border border-slate-200 bg-white p-4">
              <h3 className="text-sm font-semibold text-slate-900">Custody ledger</h3>
              <div className="space-y-3">
                {detail.recent_logs.length === 0 && (
                  <p className="text-xs text-slate-500">No custody logs recorded for this sample yet.</p>
                )}
                {detail.recent_logs.map((log) => (
                  <article
                    key={log.id}
                    className="rounded-md border border-slate-100 bg-slate-50 p-3"
                  >
                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <span className="font-medium text-slate-700">{log.custody_action}</span>
                      <span>{new Date(log.performed_at).toLocaleString()}</span>
                    </div>
                    {log.guardrail_flags.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {log.guardrail_flags.map((flag) => (
                          <span
                            key={flag}
                            className="rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-rose-600"
                          >
                            {flag}
                          </span>
                        ))}
                      </div>
                    )}
                    {log.notes && <p className="mt-2 text-xs text-slate-600">{log.notes}</p>}
                  </article>
                ))}
              </div>
            </div>
            <div className="space-y-4 rounded-md border border-slate-200 bg-white p-4">
              <h3 className="text-sm font-semibold text-slate-900">Guardrail escalations & linked records</h3>
              <div className="space-y-3">
                {detail.escalations.length === 0 && (
                  <p className="text-xs text-slate-500">No active escalations for this sample.</p>
                )}
                {detail.escalations.map((escalation) => (
                  <article
                    key={escalation.id}
                    className="rounded-md border border-amber-200 bg-amber-50 p-3"
                  >
                    <div className="flex items-center justify-between text-xs text-amber-700">
                      <span className="font-semibold uppercase">{escalation.severity}</span>
                      <span>{escalation.status}</span>
                    </div>
                    <p className="mt-1 text-sm text-amber-900">{escalation.reason}</p>
                    {escalation.due_at && (
                      <p className="mt-1 text-xs text-amber-700">
                        Due {new Date(escalation.due_at).toLocaleString()}
                      </p>
                    )}
                  </article>
                ))}
              </div>
              <div className="space-y-2">
                <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Linked planner sessions</h4>
                <div className="flex flex-wrap gap-2">
                  {detail.item.linked_planner_session_ids.length === 0 && (
                    <span className="text-xs text-slate-500">None</span>
                  )}
                  {detail.item.linked_planner_session_ids.map((sessionId) => (
                    <Link
                      key={sessionId}
                      href={`/planner/${sessionId}`}
                      className="rounded border border-slate-200 px-2 py-0.5 text-xs text-slate-700 hover:bg-slate-50"
                    >
                      Planner {sessionId.slice(0, 8)}
                    </Link>
                  ))}
                </div>
                <h4 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Linked DNA assets</h4>
                <div className="flex flex-wrap gap-2">
                  {detail.item.linked_asset_version_ids.length === 0 && (
                    <span className="text-xs text-slate-500">None</span>
                  )}
                  {detail.item.linked_asset_version_ids.map((versionId) => (
                    <Link
                      key={versionId}
                      href={`/dna-viewer/${versionId}`}
                      className="rounded border border-slate-200 px-2 py-0.5 text-xs text-slate-700 hover:bg-slate-50"
                    >
                      DNA {versionId.slice(0, 8)}
                    </Link>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </section>
    </div>
  )
}

interface SampleRowProps {
  sample: InventorySampleSummary
  selected: boolean
  onSelect: () => void
}

const SampleRow: React.FC<SampleRowProps> = ({ sample, selected, onSelect }) => {
  const badgeDetail = sample.guardrail_flags.length
    ? `${sample.guardrail_flags.length} guardrail flag${sample.guardrail_flags.length > 1 ? 's' : ''}`
    : 'No guardrail flags'

  return (
    <tr
      className={`cursor-pointer transition-colors hover:bg-slate-50 ${selected ? 'bg-slate-100' : ''}`}
      onClick={onSelect}
      data-testid="sample-row"
    >
      <td className="px-4 py-2 text-sm font-medium text-slate-800">{sample.name}</td>
      <td className="px-4 py-2">
        <GuardrailBadge
          label="Custody"
          state={sample.custody_state ?? 'idle'}
          detail={badgeDetail}
          metadataTags={sample.guardrail_flags}
        />
      </td>
      <td className="px-4 py-2 text-xs text-slate-600">
        {sample.guardrail_flags.length > 0 ? sample.guardrail_flags.join(', ') : '—'}
      </td>
      <td className="px-4 py-2 text-sm text-slate-700">{sample.open_escalations}</td>
      <td className="px-4 py-2 text-xs text-slate-500">
        {new Date(sample.updated_at).toLocaleString()}
      </td>
    </tr>
  )
}

export default SampleDashboard
