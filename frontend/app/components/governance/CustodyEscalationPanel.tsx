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
import type {
  CustodyEscalation,
  CustodyProtocolExecution,
  FreezerFaultRecord,
} from '../../types'
import { cn } from '../../utils/cn'

interface CustodyEscalationPanelProps {
  escalations: CustodyEscalation[] | undefined
  faults: FreezerFaultRecord[] | undefined
  isEscalationLoading: boolean
  isFaultLoading: boolean
  protocols?: CustodyProtocolExecution[] | undefined
  isProtocolLoading?: boolean
  escalationError?: Error | null
  faultError?: Error | null
  protocolError?: Error | null
  onAcknowledge: (id: string) => void
  onResolve: (id: string) => void
  onNotify: (id: string) => void
  busyIds?: Set<string>
}

// guardrail_status_styles: map guardrail posture to utility classes for badges
const GUARDRAIL_STATUS_TONE: Record<string, string> = {
  halted: 'border-rose-200 bg-rose-100 text-rose-700',
  alert: 'border-amber-200 bg-amber-100 text-amber-700',
  monitor: 'border-sky-200 bg-sky-100 text-sky-700',
  stabilizing: 'border-emerald-200 bg-emerald-100 text-emerald-700',
  stable: 'border-emerald-100 bg-emerald-50 text-emerald-600',
}

// sop_link: external SOP doc guiding recovery drill mitigation steps
const SOP_DOC_URL = 'https://docs.biolabs.local/operations/custody_governance'

// purpose: governance custody escalation dashboard section with SLA controls
// inputs: custody escalation queue, freezer faults, action callbacks for RBAC-aware operators
// outputs: actionable cards enabling acknowledge/notify/resolve flows aligned with guardrail heuristics
// status: pilot
export default function CustodyEscalationPanel({
  escalations,
  faults,
  isEscalationLoading,
  isFaultLoading,
  protocols,
  isProtocolLoading = false,
  escalationError,
  faultError,
  protocolError,
  onAcknowledge,
  onResolve,
  onNotify,
  busyIds,
}: CustodyEscalationPanelProps) {
  const loading = isEscalationLoading || isFaultLoading || isProtocolLoading
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
  const hasProtocols = protocols && protocols.length > 0

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
      <Card className="lg:col-span-2">
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
            <h2 className="text-lg font-semibold text-neutral-900">Protocol guardrail timeline</h2>
            <p className="text-sm text-neutral-500">
              Playback mitigation checkpoints, recovery drills, and SOP references per execution event.
            </p>
          </div>
        </CardHeader>
        <CardBody className="space-y-4">
          {protocolError ? (
            <Alert variant="error" title="Unable to load protocol guardrails">
              <p>{protocolError.message}</p>
            </Alert>
          ) : !hasProtocols ? (
            <EmptyState
              title="No protocol guardrails recorded"
              description="Escalations have not been linked to protocol executions yet."
            />
          ) : (
            <div className="space-y-3">
              {protocols!.map((protocol) => (
                <article
                  key={protocol.id}
                  className="rounded-lg border border-neutral-200 bg-white/80 p-4 shadow-sm"
                >
                  <header className="flex flex-wrap items-start justify-between gap-3">
                    <div className="space-y-1">
                      <h3 className="text-sm font-semibold text-neutral-900">
                        {protocol.template_name ?? `Execution ${protocol.id.slice(0, 8)}`}
                      </h3>
                      <p className="text-xs text-neutral-500">
                        {protocol.status} · {protocol.open_escalations} open escalation
                        {protocol.open_escalations === 1 ? '' : 's'}
                      </p>
                      {_renderLastSynced(protocol.guardrail_state)}
                    </div>
                    {_renderGuardrailStatusBadge(protocol.guardrail_status)}
                  </header>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {protocol.open_drill_count > 0 && (
                      <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700">
                        {protocol.open_drill_count} recovery drill
                        {protocol.open_drill_count === 1 ? '' : 's'} active
                      </span>
                    )}
                    {protocol.qc_backpressure && (
                      <span className="inline-flex items-center rounded-full bg-indigo-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-indigo-700">
                        QC backpressure
                      </span>
                    )}
                  </div>
                  {_renderTimelineOverlays(protocol)}
                </article>
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

function _renderGuardrailStatusBadge(status: string) {
  const tone = GUARDRAIL_STATUS_TONE[status] ?? GUARDRAIL_STATUS_TONE.stable
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold uppercase tracking-wide',
        tone,
      )}
    >
      {status}
    </span>
  )
}

function _renderLastSynced(state: Record<string, any> | null | undefined) {
  const timestamp = typeof state?.['last_synced_at'] === 'string' ? state?.['last_synced_at'] : null
  if (!timestamp) {
    return null
  }
  return (
    <p className="text-[11px] text-neutral-400">
      Last synced {new Date(timestamp).toLocaleString()}
    </p>
  )
}

function _renderTimelineOverlays(protocol: CustodyProtocolExecution) {
  const overlays = protocol.event_overlays ? Object.entries(protocol.event_overlays) : []
  if (overlays.length === 0) {
    return <p className="mt-3 text-xs text-neutral-400">No guardrail overlays recorded.</p>
  }
  return (
    <div className="mt-4 space-y-3">
      {overlays.map(([eventId, raw]) => {
        const overlay = (raw ?? {}) as Record<string, any>
        const mitigation = Array.isArray(overlay.mitigation_checklist)
          ? (overlay.mitigation_checklist as string[])
          : []
        const openEscalations = Array.isArray(overlay.open_escalation_ids)
          ? overlay.open_escalation_ids.length
          : 0
        const drillCount = typeof overlay.open_drill_count === 'number' ? overlay.open_drill_count : 0
        const severity = typeof overlay.max_severity === 'string' ? overlay.max_severity : undefined
        return (
          <div
            key={eventId}
            className="rounded border border-neutral-200 bg-neutral-50 p-3"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-xs font-semibold text-neutral-700">Event {eventId.slice(0, 8)} timeline</p>
              <div className="flex flex-wrap gap-2">
                {severity && (
                  <span className="inline-flex items-center rounded-full bg-neutral-200 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-neutral-700">
                    {severity}
                  </span>
                )}
                {openEscalations > 0 && (
                  <span className="inline-flex items-center rounded-full bg-rose-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-rose-700">
                    {openEscalations} open
                  </span>
                )}
              </div>
            </div>
            {mitigation.length > 0 ? (
              <ul className="mt-2 list-disc space-y-1 pl-4 text-[11px] text-neutral-600">
                {mitigation.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-[11px] text-neutral-500">No mitigation checklist entries.</p>
            )}
            {drillCount > 0 && (
              <p className="mt-2 text-[11px] font-semibold uppercase tracking-wide text-amber-700">
                {drillCount} drill in progress
              </p>
            )}
            <a
              className="mt-3 inline-flex items-center text-[11px] font-semibold text-indigo-600 hover:text-indigo-700"
              href={SOP_DOC_URL}
              target="_blank"
              rel="noreferrer"
            >
              Review SOP guidance
            </a>
          </div>
        )
      })}
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
