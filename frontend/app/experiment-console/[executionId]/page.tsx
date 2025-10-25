'use client'

import { useMemo, useState } from 'react'
import { useParams } from 'next/navigation'
import {
  useAdvanceExperimentStep,
  useExperimentSession,
  useUpdateExperimentStep,
} from '../../hooks/useExperimentConsole'
import api from '../../api/client'

const statusColors: Record<string, string> = {
  pending: 'bg-neutral-200 text-neutral-800',
  in_progress: 'bg-blue-100 text-blue-700',
  completed: 'bg-emerald-100 text-emerald-700',
  skipped: 'bg-amber-100 text-amber-700',
}

const anomalyBadges: Record<string, string> = {
  info: 'bg-sky-100 text-sky-700',
  warning: 'bg-amber-100 text-amber-700',
  critical: 'bg-rose-100 text-rose-700',
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

const summarizeTelemetryData = (payload?: Record<string, any> | null) => {
  if (!payload) return '—'
  const entries = Object.entries(payload)
  if (entries.length === 0) return '—'
  return entries
    .slice(0, 4)
    .map(([key, val]) => {
      if (val === null || val === undefined) return `${key}: —`
      if (typeof val === 'object') {
        try {
          return `${key}: ${JSON.stringify(val)}`
        } catch (error) {
          return `${key}: [object]`
        }
      }
      return `${key}: ${val}`
    })
    .join(' • ')
}

const formatActionLabel = (action: string) => {
  const [domain = '', verb = '', identifier = ''] = action.split(':')
  if (domain === 'inventory' && verb === 'restore') return 'Restore Inventory Availability'
  if (domain === 'inventory' && verb === 'link') return 'Link Inventory Item'
  if (domain === 'equipment' && verb === 'calibrate') return 'Confirm Calibration'
  if (domain === 'equipment' && verb === 'maintenance_request') return 'Submit Maintenance Request'
  if (domain === 'booking' && verb === 'adjust') return 'Adjust Booking Window'
  if (domain === 'compliance' && verb === 'approve') {
    return identifier ? `Record Approval: ${identifier}` : 'Record Compliance Approval'
  }
  if (domain === 'notify' && verb === 'approver') {
    return identifier ? `Notify Approver ${identifier}` : 'Notify Approver'
  }
  return action.replace(/[:_]/g, ' ')
}

export default function ExperimentConsolePage() {
  const params = useParams<{ executionId: string }>()
  const executionId = useMemo(() => {
    const param = params?.executionId
    return Array.isArray(param) ? param[0] : param
  }, [params])

  const sessionQuery = useExperimentSession(executionId ?? null)
  const stepMutation = useUpdateExperimentStep(executionId ?? null)
  const advanceMutation = useAdvanceExperimentStep(executionId ?? null)
  const [pendingAction, setPendingAction] = useState<string | null>(null)

  if (!executionId) {
    return (
      <div className="p-8">
        <h1 className="text-2xl font-semibold">Experiment Console</h1>
        <p className="mt-4 text-neutral-600">
          Provide an execution identifier to access the live experiment workspace.
        </p>
      </div>
    )
  }

  if (sessionQuery.isLoading) {
    return (
      <div className="p-8">
        <h1 className="text-2xl font-semibold">Experiment Console</h1>
        <p className="mt-4 text-neutral-600">Loading execution context…</p>
      </div>
    )
  }

  if (sessionQuery.isError || !sessionQuery.data) {
    return (
      <div className="p-8">
        <h1 className="text-2xl font-semibold">Experiment Console</h1>
        <p className="mt-4 text-red-600">Unable to load the requested execution.</p>
      </div>
    )
  }

  const session = sessionQuery.data

  const updateStep = (stepIndex: number, status: 'in_progress' | 'completed') => {
    const timestamp = new Date().toISOString()
    stepMutation.mutate({
      stepIndex,
      update:
        status === 'in_progress'
          ? { status, started_at: timestamp }
          : { status, completed_at: timestamp },
    })
  }

  const handleAdvance = async (stepIndex: number) => {
    try {
      await advanceMutation.mutateAsync({ stepIndex })
    } catch (error: any) {
      const detail = error?.response?.data
      const message =
        detail?.blocked_reason || detail?.detail || detail?.message || error?.message || 'Unable to advance step'
      if (typeof window !== 'undefined') {
        window.alert(`Unable to advance step: ${message}`)
      }
    }
  }

  const handleAction = async (action: string) => {
    let shouldRefresh = false
    setPendingAction(action)
    try {
      const [domain = '', verb = '', identifier = ''] = action.split(':')
      if (domain === 'inventory' && verb === 'restore' && identifier) {
        await api.put(`/api/inventory/items/${identifier}`, { status: 'available' })
        shouldRefresh = true
        window.alert('Inventory item restored to available')
        return
      }
      if (domain === 'equipment' && verb === 'calibrate' && identifier) {
        const dueDate = new Date(Date.now() + 2 * 24 * 60 * 60 * 1000).toISOString()
        await api.post('/api/equipment/maintenance', {
          equipment_id: identifier,
          due_date: dueDate,
          task_type: 'calibration',
          description: 'Calibration confirmed from console orchestration',
        })
        shouldRefresh = true
        window.alert('Calibration workflow logged for equipment')
        return
      }
      if (domain === 'equipment' && verb === 'maintenance_request' && identifier) {
        const dueDate = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString()
        await api.post('/api/equipment/maintenance', {
          equipment_id: identifier,
          due_date: dueDate,
          task_type: 'maintenance',
          description: 'Auto-generated maintenance request from orchestrator',
        })
        shouldRefresh = true
        window.alert('Maintenance request submitted')
        return
      }
      if (domain === 'booking') {
        window.open('/schedule', '_blank', 'noopener')
        return
      }
      if (domain === 'compliance') {
        window.open('/compliance', '_blank', 'noopener')
        return
      }
      if (domain === 'notify') {
        window.alert(formatActionLabel(action))
        return
      }
      window.alert(`No automated handler for ${formatActionLabel(action)} yet.`)
    } catch (error) {
      console.error('Failed to execute required action', error)
      window.alert('Unable to perform the requested action. Check console for details.')
    } finally {
      setPendingAction(null)
      if (shouldRefresh) {
        sessionQuery.refetch()
      }
    }
  }

    return (
      <div className="p-8 space-y-8">
        <header className="flex flex-col gap-2">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-semibold">{session.protocol.name}</h1>
            <span
              className={`text-xs font-medium px-3 py-1 rounded-full ${
                statusColors[session.execution.status] ?? statusColors.pending
              }`}
            >
              {session.execution.status.replace('_', ' ')}
            </span>
          </div>
          <p className="text-neutral-600">
            Version {session.protocol.version} • Started{' '}
            {formatDateTime(session.execution.created_at)}
          </p>
        </header>

        {session.telemetry_channels.length > 0 && (
          <section className="border border-neutral-200 rounded-lg bg-white shadow-sm p-4 space-y-4">
            <div className="flex items-center justify-between gap-4">
              <h2 className="text-xl font-semibold">Live Instrument Channels</h2>
              <span className="text-sm text-neutral-500">
                Auto-logged snapshots refresh with each telemetry ping.
              </span>
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              {session.telemetry_channels.map((channel) => (
                <article
                  key={channel.equipment.id}
                  className="border border-neutral-100 rounded-md p-3 space-y-2"
                >
                  <header className="flex items-center justify-between">
                    <div>
                      <p className="text-sm font-semibold text-neutral-800">
                        {channel.equipment.name}
                      </p>
                      <p className="text-xs text-neutral-500 uppercase tracking-wide">
                        {channel.equipment.eq_type}
                      </p>
                    </div>
                    <span className="text-xs font-medium px-2 py-1 rounded-full border border-neutral-200">
                      {channel.status ?? 'unknown'}
                    </span>
                  </header>
                  <dl className="space-y-1 text-xs text-neutral-600">
                    <div>
                      <dt className="font-medium text-neutral-500">Streams</dt>
                      <dd>{channel.stream_topics.length ? channel.stream_topics.join(', ') : '—'}</dd>
                    </div>
                    <div>
                      <dt className="font-medium text-neutral-500">Last Reading</dt>
                      <dd>
                        {formatDateTime(channel.latest_reading?.timestamp ?? undefined)}
                      </dd>
                    </div>
                    <div>
                      <dt className="font-medium text-neutral-500">Snapshot</dt>
                      <dd className="text-neutral-700">
                        {summarizeTelemetryData(channel.latest_reading?.data)}
                      </dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          </section>
        )}

        <section className="grid grid-cols-1 xl:grid-cols-3 gap-6 items-start">
          <div className="xl:col-span-2 space-y-4">
            <h2 className="text-xl font-semibold">Protocol Steps</h2>
            <div className="space-y-4">
              {session.steps.map((step) => {
                const isStepBlocked = Boolean(step.blocked_reason && step.status === 'pending')
                const isTerminal = step.status === 'completed' || step.status === 'skipped'
                const isInProgress = step.status === 'in_progress'
                return (
                  <article
                    key={step.index}
                    className="border border-neutral-200 rounded-lg p-4 bg-white shadow-sm"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <h3 className="text-lg font-medium">Step {step.index + 1}</h3>
                        <p className="text-neutral-600 whitespace-pre-wrap mt-1">
                          {step.instruction}
                        </p>
                      </div>
                      <span
                        className={`text-xs font-semibold px-3 py-1 rounded-full ${
                          statusColors[step.status] ?? statusColors.pending
                        }`}
                      >
                        {step.status.replace('_', ' ')}
                      </span>
                    </div>
                    <dl className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-sm text-neutral-600">
                      <div>
                        <dt className="font-medium text-neutral-500">Started</dt>
                        <dd>{formatDateTime(step.started_at ?? undefined)}</dd>
                      </div>
                      <div>
                        <dt className="font-medium text-neutral-500">Completed</dt>
                        <dd>{formatDateTime(step.completed_at ?? undefined)}</dd>
                      </div>
                    </dl>
                    {isStepBlocked && (
                      <div className="mt-4 border border-rose-200 bg-rose-50 rounded-md p-3 space-y-2">
                        <p className="text-sm font-semibold text-rose-700">Blocked by orchestration</p>
                        <p className="text-sm text-rose-600">{step.blocked_reason}</p>
                        {step.required_actions.length > 0 && (
                          <div className="space-y-2">
                            <p className="text-xs uppercase tracking-wide text-rose-500">Required Actions</p>
                            <div className="flex flex-wrap gap-2">
                              {step.required_actions.map((action) => (
                                <button
                                  key={action}
                                  onClick={() => handleAction(action)}
                                  disabled={pendingAction === action}
                                  className="text-xs font-medium px-3 py-2 rounded-md border border-rose-200 bg-white text-rose-700 hover:bg-rose-100 transition-colors disabled:opacity-60"
                                >
                                  {formatActionLabel(action)}
                                </button>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}
                    {step.auto_triggers.length > 0 && (
                      <div className="mt-3 space-y-1">
                        <p className="text-xs uppercase tracking-wide text-blue-500">Suggested Automations</p>
                        <div className="flex flex-wrap gap-2">
                          {step.auto_triggers.map((trigger) => (
                            <span
                              key={trigger}
                              className="text-xs font-medium px-2 py-1 rounded-full bg-blue-50 text-blue-700 border border-blue-200"
                            >
                              {formatActionLabel(trigger)}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                    <div className="flex flex-wrap gap-3 mt-4">
                      <button
                        onClick={() => updateStep(step.index, 'in_progress')}
                        disabled={stepMutation.isPending || isStepBlocked || step.status !== 'pending'}
                        className="text-sm px-3 py-2 rounded-md bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-60"
                      >
                        Mark In Progress
                      </button>
                      <button
                        onClick={() => updateStep(step.index, 'completed')}
                        disabled={stepMutation.isPending || !isInProgress}
                        className="text-sm px-3 py-2 rounded-md bg-emerald-600 text-white hover:bg-emerald-700 transition-colors disabled:opacity-60"
                      >
                        Mark Complete
                      </button>
                      <button
                        onClick={() => handleAdvance(step.index)}
                        disabled={advanceMutation.isPending || isStepBlocked || isTerminal}
                        className="text-sm px-3 py-2 rounded-md border border-blue-300 text-blue-700 bg-blue-50 hover:bg-blue-100 transition-colors disabled:opacity-60"
                      >
                        Attempt Orchestrated Advance
                      </button>
                    </div>
                  </article>
                )
              })}
            </div>
          </div>

          <aside className="space-y-6">
            <section className="border border-neutral-200 rounded-lg bg-white shadow-sm p-4 space-y-3">
              <h2 className="text-lg font-semibold">Telemetry Anomalies</h2>
              {session.anomaly_events.length === 0 ? (
                <p className="text-sm text-neutral-600">
                  No deviations detected in the latest telemetry window.
                </p>
              ) : (
                <ul className="space-y-2 text-sm text-neutral-700">
                  {session.anomaly_events.map((event, index) => (
                    <li key={`${event.equipment_id}-${event.timestamp}-${index}`} className="border border-neutral-100 rounded-md p-2">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium text-neutral-800">
                          Channel {event.channel}
                        </span>
                        <span
                          className={`text-xs font-semibold px-2 py-1 rounded-full ${
                            anomalyBadges[event.severity] ?? anomalyBadges.warning
                          }`}
                        >
                          {event.severity}
                        </span>
                      </div>
                      <p className="text-sm text-neutral-700 mt-1">{event.message}</p>
                      <p className="text-xs text-neutral-500 mt-1">
                        Logged {formatDateTime(event.timestamp)}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="border border-neutral-200 rounded-lg bg-white shadow-sm p-4 space-y-3">
              <h2 className="text-lg font-semibold">Auto Notebook Entries</h2>
              {session.auto_log_entries.length === 0 ? (
                <p className="text-sm text-neutral-600">
                  Telemetry snapshots will appear here for review before publishing to the lab notebook.
                </p>
              ) : (
                <ul className="space-y-2 text-sm text-neutral-700">
                  {session.auto_log_entries.map((entry, index) => (
                    <li key={`${entry.source}-${entry.created_at}-${index}`} className="flex flex-col border border-neutral-100 rounded-md p-2">
                      <span className="font-medium text-neutral-800">{entry.title}</span>
                      <span className="text-xs text-neutral-500">
                        {entry.source} • {formatDateTime(entry.created_at)}
                      </span>
                      {entry.body && (
                        <p className="text-sm text-neutral-700 mt-1 whitespace-pre-wrap">
                          {entry.body}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="border border-neutral-200 rounded-lg bg-white shadow-sm p-4 space-y-3">
              <h2 className="text-lg font-semibold">Inventory Pull Sheet</h2>
              {session.inventory_items.length === 0 ? (
                <p className="text-sm text-neutral-600">No inventory linked to this run yet.</p>
              ) : (
              <ul className="space-y-2 text-sm text-neutral-700">
                {session.inventory_items.map((item) => (
                  <li key={item.id} className="flex flex-col border border-neutral-100 rounded-md p-2">
                    <span className="font-medium">{item.name}</span>
                    <span className="text-xs text-neutral-500 uppercase tracking-wide">
                      {item.item_type}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="border border-neutral-200 rounded-lg bg-white shadow-sm p-4 space-y-3">
            <h2 className="text-lg font-semibold">Instrumentation Schedule</h2>
            {session.bookings.length === 0 ? (
              <p className="text-sm text-neutral-600">No bookings reserved for this execution.</p>
            ) : (
              <ul className="space-y-2 text-sm text-neutral-700">
                {session.bookings.map((booking) => (
                  <li key={booking.id} className="border border-neutral-100 rounded-md p-2">
                    <p className="font-medium">Resource #{booking.resource_id.slice(0, 6)}</p>
                    <p className="text-xs text-neutral-500">
                      {formatDateTime(booking.start_time)} → {formatDateTime(booking.end_time)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="border border-neutral-200 rounded-lg bg-white shadow-sm p-4 space-y-3">
            <h2 className="text-lg font-semibold">Notebook Trail</h2>
            {session.notebook_entries.length === 0 ? (
              <p className="text-sm text-neutral-600">No notebook entries recorded yet.</p>
            ) : (
              <ul className="space-y-2 text-sm text-neutral-700">
                {session.notebook_entries.map((entry) => (
                  <li key={entry.id} className="flex flex-col border border-neutral-100 rounded-md p-2">
                    <span className="font-medium">{entry.title}</span>
                    <span className="text-xs text-neutral-500">
                      Updated {formatDateTime(entry.updated_at)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </section>
    </div>
  )
}
