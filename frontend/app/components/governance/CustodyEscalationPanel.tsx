'use client'

import React from 'react'
import {
  Alert,
  Button,
  Card,
  CardBody,
  CardHeader,
  EmptyState,
  LoadingState,
} from '../ui'
import type { CustodyEscalation, FreezerFaultRecord } from '../../types'
import { cn } from '../../utils/cn'

interface CustodyEscalationPanelProps {
  escalations: CustodyEscalation[] | undefined
  faults: FreezerFaultRecord[] | undefined
  isEscalationLoading: boolean
  isFaultLoading: boolean
  escalationError?: Error | null
  faultError?: Error | null
  onAcknowledge: (id: string) => void
  onResolve: (id: string) => void
  onNotify: (id: string) => void
  busyIds?: Set<string>
}

// purpose: governance custody escalation dashboard section with SLA controls
// inputs: custody escalation queue, freezer faults, action callbacks for RBAC-aware operators
// outputs: actionable cards enabling acknowledge/notify/resolve flows aligned with guardrail heuristics
// status: pilot
export default function CustodyEscalationPanel({
  escalations,
  faults,
  isEscalationLoading,
  isFaultLoading,
  escalationError,
  faultError,
  onAcknowledge,
  onResolve,
  onNotify,
  busyIds,
}: CustodyEscalationPanelProps) {
  const loading = isEscalationLoading || isFaultLoading
  if (loading) {
    return <LoadingState title="Loading custody escalations" />
  }

  if (escalationError) {
    return (
      <Alert variant="error" title="Unable to load custody escalations">
        <p>{escalationError.message}</p>
      </Alert>
    )
  }

  const hasEscalations = escalations && escalations.length > 0

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-1">
            <h2 className="text-lg font-semibold text-neutral-900">Custody escalations</h2>
            <p className="text-sm text-neutral-500">
              SLA-driven escalation queue with guardrail context. Actions respect governance RBAC enforcement.
            </p>
          </div>
        </CardHeader>
        <CardBody className="space-y-4">
          {!hasEscalations ? (
            <EmptyState
              title="No active custody escalations"
              description="Guardrails are green. Continue monitoring freezer capacity and lineage dashboards."
            />
          ) : (
            <div className="space-y-3">
              {escalations!.map((escalation) => (
                <section
                  key={escalation.id}
                  className={cn(
                    'rounded-lg border p-4 shadow-sm transition-colors',
                    escalation.severity === 'critical'
                      ? 'border-rose-200 bg-rose-50'
                      : escalation.severity === 'warning'
                      ? 'border-amber-200 bg-amber-50'
                      : 'border-sky-200 bg-sky-50',
                  )}
                >
                    <header className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <h3 className="text-sm font-semibold text-neutral-900">{_resolveEscalationTitle(escalation)}</h3>
                        <p className="text-xs text-neutral-500">{escalation.reason}</p>
                        {_renderProtocolContext(escalation)}
                        {_renderRecoveryBadge(escalation)}
                      </div>
                      <span className="text-xs font-semibold uppercase tracking-wide text-neutral-600">
                        {escalation.status}
                      </span>
                    </header>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {escalation.guardrail_flags.map((flag) => (
                      <span
                        key={flag}
                        className="inline-flex items-center rounded-full border border-red-200 bg-red-50 px-2 py-0.5 text-xs font-semibold text-red-700"
                      >
                        {flag}
                      </span>
                    ))}
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {escalation.status === 'open' && (
                      <Button
                        size="sm"
                        variant="primary"
                        onClick={() => onAcknowledge(escalation.id)}
                        disabled={busyIds?.has(escalation.id)}
                      >
                        Acknowledge
                      </Button>
                    )}
                    {(escalation.status === 'open' || escalation.status === 'acknowledged') && (
                      <Button
                        size="sm"
                        variant="secondary"
                        onClick={() => onNotify(escalation.id)}
                        disabled={busyIds?.has(escalation.id)}
                      >
                        Notify team
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => onResolve(escalation.id)}
                      disabled={busyIds?.has(escalation.id)}
                    >
                      Resolve
                    </Button>
                  </div>
                  <dl className="mt-4 grid grid-cols-2 gap-2 text-xs text-neutral-500">
                    <div>
                      <dt className="font-semibold uppercase tracking-wide">Due</dt>
                      <dd>{_formatDate(escalation.due_at)}</dd>
                    </div>
                    <div>
                      <dt className="font-semibold uppercase tracking-wide">Updated</dt>
                      <dd>{_formatDate(escalation.updated_at)}</dd>
                    </div>
                  </dl>
                </section>
              ))}
            </div>
          )}
        </CardBody>
      </Card>
      <Card>
        <CardHeader>
          <div className="flex flex-col gap-1">
            <h2 className="text-lg font-semibold text-neutral-900">Freezer health incidents</h2>
            <p className="text-sm text-neutral-500">
              Fault telemetry sourced from custody guardrails to coordinate mitigation playbooks.
            </p>
          </div>
        </CardHeader>
        <CardBody className="space-y-4">
          {faultError ? (
            <Alert variant="error" title="Unable to load freezer faults">
              <p>{faultError.message}</p>
            </Alert>
          ) : !faults || faults.length === 0 ? (
            <EmptyState
              title="No freezer faults detected"
              description="All monitored freezers report healthy telemetry."
            />
          ) : (
            <ul className="space-y-3">
              {faults.map((fault) => (
                <li
                  key={fault.id}
                  className={cn(
                    'rounded-lg border p-4 shadow-sm',
                    fault.resolved_at ? 'border-neutral-200 bg-white' : 'border-amber-200 bg-amber-50',
                  )}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-sm font-semibold text-neutral-800">{fault.fault_type}</p>
                      <p className="text-xs text-neutral-500">
                        Detected {new Date(fault.occurred_at).toLocaleString()}
                      </p>
                    </div>
                    <span className="text-xs font-semibold uppercase tracking-wide text-amber-700">
                      {fault.severity}
                    </span>
                  </div>
                  {fault.guardrail_flag && (
                    <p className="mt-2 text-xs text-neutral-500">Flag: {fault.guardrail_flag}</p>
                  )}
                  {fault.resolved_at && (
                    <p className="mt-1 text-xs text-neutral-400">
                      Resolved {new Date(fault.resolved_at).toLocaleString()}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </div>
  )
}

function _resolveEscalationTitle(escalation: CustodyEscalation) {
  const statusLabel = escalation.status === 'open' ? 'Action required' : escalation.status
  return `${statusLabel} · ${escalation.severity}`
}

function _renderProtocolContext(escalation: CustodyEscalation) {
  const context = escalation.protocol_execution
  if (!context && !escalation.protocol_execution_id) {
    return null
  }
  const executionLabel = context?.template_name
    ? `${context.template_name} · ${context.status}`
    : `Execution ${escalation.protocol_execution_id}`
  return (
    <p className="mt-1 text-[11px] text-neutral-500">
      Protocol: {executionLabel}
    </p>
  )
}

function _renderRecoveryBadge(escalation: CustodyEscalation) {
  if (!escalation.meta?.recovery_drill_open) {
    return null
  }
  return (
    <p className="mt-1 inline-flex items-center rounded bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700">
      Recovery drill active
    </p>
  )
}

function _formatDate(value: string | null) {
  if (!value) {
    return 'Not set'
  }
  return new Date(value).toLocaleString()
}
