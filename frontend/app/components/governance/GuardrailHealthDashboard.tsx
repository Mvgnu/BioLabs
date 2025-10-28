'use client'

import React, { useMemo } from 'react'
import { Alert, Card, CardBody, CardHeader, EmptyState, LoadingState } from '../ui'
import type {
  GovernanceGuardrailHealthReport,
  GovernanceGuardrailQueueEntry,
} from '../../types'
import { cn } from '../../utils/cn'

interface GuardrailHealthDashboardProps {
  report?: GovernanceGuardrailHealthReport
  isLoading: boolean
  error?: Error | null
}

// purpose: render guardrail enforcement health metrics for governance operators
// inputs: guardrail health report payload, loading + error flags from React Query
// outputs: dashboard cards and queue table highlighting blocked or delayed exports
// status: pilot
export default function GuardrailHealthDashboard({
  report,
  isLoading,
  error,
}: GuardrailHealthDashboardProps) {
  const totals = report?.totals
  const breakdown = useMemo(() => {
    if (!report?.state_breakdown) return [] as Array<[string, number]>
    return Object.entries(report.state_breakdown)
      .sort(([, a], [, b]) => Number(b) - Number(a))
      .slice(0, 6)
  }, [report?.state_breakdown])

  const queueEntries = report?.queue ?? []

  if (isLoading) {
    return <LoadingState title="Loading guardrail health" />
  }

  if (error) {
    return (
      <Alert variant="error" title="Failed to load guardrail health">
        <p>{error.message}</p>
      </Alert>
    )
  }

  if (!totals || totals.total_exports === 0) {
    return (
      <EmptyState
        title="No guardrail activity yet"
        description="Queue telemetry will appear once narrative exports attempt packaging."
      />
    )
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-4">
        <MetricCard
          label="Exports tracked"
          value={totals.total_exports}
          description="Narrative exports with guardrail queue telemetry."
        />
        <MetricCard
          label="Blocked"
          value={totals.blocked}
          accent="danger"
          description="Exports currently halted by guardrail forecasts."
        />
        <MetricCard
          label="Awaiting approval"
          value={totals.awaiting_approval}
          description="Exports paused until staged approvals complete."
        />
        <MetricCard
          label="Queued"
          value={totals.queued}
          description="Ready for packaging once workers process the queue."
        />
      </div>

      <Card>
        <CardHeader>
          <div>
            <h2 className="text-lg font-semibold text-neutral-900">State breakdown</h2>
            <p className="text-sm text-neutral-500">
              Snapshot of recent guardrail dispatch outcomes across governance surfaces.
            </p>
          </div>
        </CardHeader>
        <CardBody>
          {breakdown.length === 0 ? (
            <p className="text-sm text-neutral-500">No guardrail telemetry recorded yet.</p>
          ) : (
            <dl className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
              {breakdown.map(([state, count]) => (
                <div key={state} className="rounded-md border border-neutral-200 p-3">
                  <dt className="text-sm font-medium text-neutral-600">{formatStateLabel(state)}</dt>
                  <dd className="text-xl font-semibold text-neutral-900">{count}</dd>
                </div>
              ))}
            </dl>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <div>
            <h2 className="text-lg font-semibold text-neutral-900">Guardrail queue</h2>
            <p className="text-sm text-neutral-500">
              Latest exports by severity with guardrail reasons, pending stages, and timestamps.
            </p>
          </div>
        </CardHeader>
        <CardBody className="overflow-x-auto p-0">
          <table className="min-w-full divide-y divide-neutral-200 text-sm">
            <thead className="bg-neutral-50">
              <tr>
                <th className="px-4 py-2 text-left font-semibold text-neutral-600">Export</th>
                <th className="px-4 py-2 text-left font-semibold text-neutral-600">State</th>
                <th className="px-4 py-2 text-left font-semibold text-neutral-600">Guardrail</th>
                <th className="px-4 py-2 text-left font-semibold text-neutral-600">Pending stage</th>
                <th className="px-4 py-2 text-left font-semibold text-neutral-600">Updated</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {queueEntries.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-sm text-neutral-500">
                    No guardrail queue entries were returned.
                  </td>
                </tr>
              ) : (
                queueEntries.map((entry) => <QueueRow key={entry.export_id} entry={entry} />)
              )}
            </tbody>
          </table>
        </CardBody>
      </Card>
    </div>
  )
}

interface MetricCardProps {
  label: string
  value: number
  description: string
  accent?: 'default' | 'danger'
}

function MetricCard({ label, value, description, accent = 'default' }: MetricCardProps) {
  return (
    <Card className={cn('border-neutral-200', accent === 'danger' ? 'border-rose-200' : undefined)}>
      <CardBody>
        <p className="text-sm font-medium text-neutral-500">{label}</p>
        <p
          className={cn(
            'mt-1 text-3xl font-semibold',
            accent === 'danger' ? 'text-rose-600' : 'text-neutral-900',
          )}
        >
          {value}
        </p>
        <p className="mt-2 text-sm text-neutral-500">{description}</p>
      </CardBody>
    </Card>
  )
}

function QueueRow({ entry }: { entry: GovernanceGuardrailQueueEntry }) {
  const stateLabel = formatStateLabel(entry.state)
  const guardrailReasons = Array.isArray(entry.context?.reasons)
    ? (entry.context.reasons as string[])
    : []
  const pendingStage = formatPendingStage(entry)
  const guardrailBadge = entry.guardrail_state
    ? entry.guardrail_state === 'blocked'
      ? { label: 'Guardrail blocked', className: 'bg-rose-100 text-rose-700' }
      : { label: 'Guardrail clear', className: 'bg-emerald-100 text-emerald-700' }
    : null
  const stateBadgeClass =
    entry.state === 'guardrail_blocked'
      ? 'bg-rose-100 text-rose-700'
      : entry.state === 'awaiting_approval'
        ? 'bg-amber-100 text-amber-700'
        : 'bg-neutral-100 text-neutral-700'

  return (
    <tr className="bg-white">
      <td className="px-4 py-3 font-mono text-xs text-neutral-600">{entry.export_id}</td>
      <td className="px-4 py-3">
        <span
          className={cn(
            'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
            stateBadgeClass,
          )}
          title={`Dispatch state: ${stateLabel}`}
        >
          {stateLabel}
        </span>
      </td>
      <td className="px-4 py-3 text-neutral-600">
        {guardrailBadge ? (
          <div className="space-y-1">
            <span
              className={cn(
                'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
                guardrailBadge.className,
              )}
            >
              {guardrailBadge.label}
            </span>
            {entry.projected_delay_minutes != null && entry.projected_delay_minutes > 0 && (
              <p className="text-xs text-neutral-500">
                Projected delay: {Math.round(entry.projected_delay_minutes)} min
              </p>
            )}
            {guardrailReasons.length > 0 && (
              <ul className="text-xs text-neutral-500">
                {guardrailReasons.map((reason) => (
                  <li key={reason}>{reason}</li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <span className="text-xs text-neutral-500">No guardrail forecast</span>
        )}
      </td>
      <td className="px-4 py-3 text-neutral-600">{pendingStage}</td>
      <td className="px-4 py-3 text-neutral-600">
        {entry.updated_at ? new Date(entry.updated_at).toLocaleString() : 'n/a'}
      </td>
    </tr>
  )
}

function formatPendingStage(entry: GovernanceGuardrailQueueEntry): string {
  const index = entry.pending_stage_index
  const status = entry.pending_stage_status
  if (index == null && !status) {
    return 'n/a'
  }
  const labelParts = [] as string[]
  if (index != null) {
    labelParts.push(`Stage ${Number(index) + 1}`)
  }
  if (status) {
    labelParts.push(`(${status})`)
  }
  if (entry.pending_stage_due_at) {
    labelParts.push(`due ${new Date(entry.pending_stage_due_at).toLocaleString()}`)
  }
  return labelParts.join(' ')
}

function formatStateLabel(state: string): string {
  return state
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}
