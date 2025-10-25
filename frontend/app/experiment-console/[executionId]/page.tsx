'use client'

import { useMemo } from 'react'
import { useParams } from 'next/navigation'
import { useExperimentSession, useUpdateExperimentStep } from '../../hooks/useExperimentConsole'

const statusColors: Record<string, string> = {
  pending: 'bg-neutral-200 text-neutral-800',
  in_progress: 'bg-blue-100 text-blue-700',
  completed: 'bg-emerald-100 text-emerald-700',
  skipped: 'bg-amber-100 text-amber-700',
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

export default function ExperimentConsolePage() {
  const params = useParams<{ executionId: string }>()
  const executionId = useMemo(() => {
    const param = params?.executionId
    return Array.isArray(param) ? param[0] : param
  }, [params])

  const sessionQuery = useExperimentSession(executionId ?? null)
  const stepMutation = useUpdateExperimentStep(executionId ?? null)

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

      <section className="grid grid-cols-1 xl:grid-cols-3 gap-6 items-start">
        <div className="xl:col-span-2 space-y-4">
          <h2 className="text-xl font-semibold">Protocol Steps</h2>
          <div className="space-y-4">
            {session.steps.map((step) => (
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
                <div className="flex flex-wrap gap-3 mt-4">
                  <button
                    onClick={() => updateStep(step.index, 'in_progress')}
                    disabled={stepMutation.isPending}
                    className="text-sm px-3 py-2 rounded-md bg-blue-600 text-white hover:bg-blue-700 transition-colors disabled:opacity-60"
                  >
                    Mark In Progress
                  </button>
                  <button
                    onClick={() => updateStep(step.index, 'completed')}
                    disabled={stepMutation.isPending}
                    className="text-sm px-3 py-2 rounded-md bg-emerald-600 text-white hover:bg-emerald-700 transition-colors disabled:opacity-60"
                  >
                    Mark Complete
                  </button>
                </div>
              </article>
            ))}
          </div>
        </div>

        <aside className="space-y-6">
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
