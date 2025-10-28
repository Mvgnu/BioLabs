'use client'

import React, { useMemo } from 'react'
import { Alert, Card, CardBody, CardHeader, EmptyState, LoadingState } from '../ui'
import type {
  GovernanceOverdueStageSample,
  GovernanceOverdueStageSummary,
  GovernanceStageMetrics,
} from '../../types'
import { cn } from '../../utils/cn'

interface OverdueDashboardProps {
  summary?: GovernanceOverdueStageSummary
  stageMetrics?: Record<string, GovernanceStageMetrics>
  isLoading: boolean
  error?: Error | null
}

// purpose: visualise overdue governance ladders with actionable escalation guidance
// inputs: overdue stage summary + per-export metrics derived from analytics meta
// outputs: operator-facing dashboard cards and tables with escalation affordances
// status: pilot
export default function OverdueDashboard({
  summary,
  stageMetrics,
  isLoading,
  error,
}: OverdueDashboardProps) {
  const sortedRoles = useMemo(() => {
    if (!summary) return [] as Array<[string, number]>
    return Object.entries(summary.role_counts)
      .sort(([, a], [, b]) => Number(b) - Number(a))
      .slice(0, 5)
  }, [summary])

  const samples = useMemo(() => {
    if (!summary) return [] as GovernanceOverdueStageSample[]
    return summary.stage_samples.slice(0, 8)
  }, [summary])

  const exportMetrics = useMemo(() => {
    if (!stageMetrics) return [] as Array<[string, GovernanceStageMetrics]>
    return Object.entries(stageMetrics).sort(([, a], [, b]) => {
      return Number(b.overdue_count ?? 0) - Number(a.overdue_count ?? 0)
    })
  }, [stageMetrics])

  if (isLoading) {
    return <LoadingState title="Loading overdue governance analytics" />
  }

  if (error) {
    return (
      <Alert variant="error" title="Failed to load analytics">
        <p>{error.message}</p>
      </Alert>
    )
  }

  if (!summary || summary.total_overdue === 0) {
    return (
      <EmptyState
        title="No overdue ladders detected"
        description="All staged approvals are meeting their SLA targets. Continue monitoring guardrail dashboards for future escalations."
      />
    )
  }

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard
          label="Overdue stages"
          value={summary.total_overdue}
          description="Stages that have breached their SLA in the last monitoring window."
        />
        <MetricCard
          label="Active breaches"
          value={summary.open_overdue}
          description="Stages still awaiting action. Escalate immediately if above tolerance."
        />
        <MetricCard
          label="Mean open minutes"
          value={summary.mean_open_minutes ?? 0}
          formatter={formatMinutes}
          description="Average duration overdue stages have remained unresolved."
        />
      </div>

      <Card>
        <CardHeader className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-neutral-900">Role pressure map</h2>
            <p className="text-sm text-neutral-500">
              Highest volume of overdue approvals by required role across all executions.
            </p>
          </div>
          <span className="text-xs uppercase tracking-wide text-neutral-400" title="Refer to docs/governance/operator_sop.md for escalation playbooks">
            Escalate via SOP
          </span>
        </CardHeader>
        <CardBody>
          {sortedRoles.length === 0 ? (
            <p className="text-sm text-neutral-500">No role-specific breaches detected.</p>
          ) : (
            <ul className="divide-y divide-neutral-200">
              {sortedRoles.map(([role, count]) => (
                <li key={role} className="flex items-center justify-between py-2">
                  <span className="font-medium text-neutral-700">{role || 'Unassigned role'}</span>
                  <span className="text-sm font-semibold text-primary-600" title="Number of overdue stages currently requiring this role">
                    {count}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <div>
            <h2 className="text-lg font-semibold text-neutral-900">Overdue stage queue</h2>
            <p className="text-sm text-neutral-500">
              Most recent overdue stages. Trigger escalation directly from the governance exports workspace.
            </p>
          </div>
        </CardHeader>
        <CardBody className="overflow-x-auto p-0">
          <table className="min-w-full divide-y divide-neutral-200 text-sm">
            <thead className="bg-neutral-50">
              <tr>
                <th scope="col" className="px-4 py-2 text-left font-semibold text-neutral-600">
                  Export
                </th>
                <th scope="col" className="px-4 py-2 text-left font-semibold text-neutral-600">
                  Stage
                </th>
                <th scope="col" className="px-4 py-2 text-left font-semibold text-neutral-600">
                  Role
                </th>
                <th scope="col" className="px-4 py-2 text-left font-semibold text-neutral-600">
                  Detected
                </th>
                <th scope="col" className="px-4 py-2 text-left font-semibold text-neutral-600">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {samples.map((sample) => (
                <tr key={sample.stage_id} className="bg-white">
                  <td className="px-4 py-3 font-mono text-xs text-neutral-600">
                    {sample.export_id}
                  </td>
                  <td className="px-4 py-3 text-neutral-700">
                    Stage {sample.sequence_index + 1} ({sample.status})
                  </td>
                  <td className="px-4 py-3 text-neutral-600">{sample.role ?? 'n/a'}</td>
                  <td className="px-4 py-3 text-neutral-600">
                    {new Date(sample.detected_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <a
                      href={`mailto:governance-ops@biolabs.local?subject=Escalate%20export%20${sample.export_id}`}
                      className="inline-flex items-center rounded-md border border-primary-500 px-3 py-1 text-xs font-semibold text-primary-600 transition hover:bg-primary-50"
                      title="Email governance operators to escalate this overdue stage per SOP guidance."
                    >
                      Escalate
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {samples.length === 0 && (
            <div className="p-6 text-sm text-neutral-500">
              All overdue stages have already been resolved.
            </div>
          )}
        </CardBody>
      </Card>

      {exportMetrics.length > 0 && (
        <Card>
          <CardHeader>
            <div>
              <h2 className="text-lg font-semibold text-neutral-900">Export-level guardrail metrics</h2>
              <p className="text-sm text-neutral-500">
                Track overdue counts, breach ratios, and resolution performance per export to prioritise operator follow-up.
              </p>
            </div>
          </CardHeader>
          <CardBody className="space-y-4">
            {exportMetrics.map(([exportId, metrics]) => (
              <div key={exportId} className="rounded-lg border border-neutral-200 p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-mono text-xs text-neutral-500">Export</p>
                    <p className="font-semibold text-neutral-800">{exportId}</p>
                  </div>
                  <div className="flex items-center gap-6">
                    <span className="text-sm text-neutral-600" title="Stages associated with this export">
                      Total stages: <strong>{metrics.total}</strong>
                    </span>
                    <span className="text-sm text-primary-600" title="Overdue stages recorded for this export">
                      Overdue: <strong>{metrics.overdue_count}</strong>
                    </span>
                    <span className="text-sm text-neutral-600" title="Average resolution time across completed stages">
                      Mean resolution: <strong>{formatMinutes(metrics.mean_resolution_minutes ?? 0)}</strong>
                    </span>
                  </div>
                </div>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  {Object.entries(metrics.stage_details).map(([stageId, detail]) => (
                    <div key={stageId} className={cn('rounded-md border px-3 py-2 text-sm', detail.breached ? 'border-orange-400 bg-orange-50' : 'border-neutral-200 bg-neutral-50')}>
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-neutral-700">Stage {stageId}</span>
                        <span className="text-xs uppercase tracking-wide text-neutral-500">{detail.status}</span>
                      </div>
                      <div className="mt-1 text-xs text-neutral-600">
                        <p>Due: {detail.due_at ? new Date(detail.due_at).toLocaleString() : 'n/a'}</p>
                        <p title="Minutes between stage start and completion">
                          Resolution: {detail.resolution_minutes != null ? `${Math.round(detail.resolution_minutes)} min` : 'pending'}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </CardBody>
        </Card>
      )}
    </div>
  )
}

interface MetricCardProps {
  label: string
  value: number
  description: string
  formatter?: (value: number) => string
}

function MetricCard({ label, value, description, formatter }: MetricCardProps) {
  const displayValue = formatter ? formatter(value) : value.toLocaleString()
  return (
    <Card className="border-primary-100 bg-primary-50">
      <CardBody>
        <p className="text-sm font-medium text-primary-700" title={description}>
          {label}
        </p>
        <p className="mt-2 text-3xl font-semibold text-primary-900">{displayValue}</p>
        <p className="mt-1 text-xs text-primary-700/80">{description}</p>
      </CardBody>
    </Card>
  )
}

function formatMinutes(value: number): string {
  if (!Number.isFinite(value)) {
    return 'n/a'
  }
  const minutes = Math.max(0, Math.round(value))
  if (minutes < 60) {
    return `${minutes} min`
  }
  const hours = minutes / 60
  return `${hours.toFixed(1)} hr`
}
