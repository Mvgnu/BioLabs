'use client'

import React, { useMemo, useState } from 'react'

import {
  useInstrumentProfiles,
  useInstrumentRuns,
  useInstrumentRunEnvelope,
  useSimulateRun,
  useSimulationEventStream,
} from '../hooks/useInstrumentation'
import type { InstrumentProfile, InstrumentSimulationEvent } from '../types'

// purpose: render robotic instrumentation digital twin dashboard with simulation workflows
// status: experimental

const scenarios = [
  { value: 'thermal_cycle', label: 'Thermal Cycling' },
  { value: 'incubation_qc', label: 'Incubation QC' },
]

export default function InstrumentationDigitalTwinPage() {
  const { data: profiles } = useInstrumentProfiles()
  const [selectedEquipmentId, setSelectedEquipmentId] = useState<string | null>(null)
  const [scenario, setScenario] = useState<string>('thermal_cycle')

  const selectedProfile: InstrumentProfile | undefined = useMemo(() => {
    if (!profiles || profiles.length === 0) {
      return undefined
    }
    return profiles.find((profile) => profile.equipment_id === selectedEquipmentId) ?? profiles[0]
  }, [profiles, selectedEquipmentId])

  const normalizedEquipmentId = selectedProfile?.equipment_id ?? null
  const { data: runs } = useInstrumentRuns(normalizedEquipmentId)
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)
  const effectiveRunId = selectedRunId ?? selectedProfile?.active_run?.id ?? null
  const { data: envelope } = useInstrumentRunEnvelope(effectiveRunId)

  const simulationMutation = useSimulateRun({ equipmentId: normalizedEquipmentId ?? '' })
  const events: InstrumentSimulationEvent[] = useSimulationEventStream(
    simulationMutation.data?.events,
    envelope ?? null,
  )

  const runTelemetry = envelope?.samples ?? []

  const triggerSimulation = () => {
    if (!normalizedEquipmentId) {
      return
    }
    simulationMutation.mutate({ scenario })
  }

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">Instrumentation Digital Twin</h1>
        <p className="text-sm text-neutral-500">
          Visualize real-time instrument state, telemetry checkpoints, and guardrail context. Run deterministic
          simulations to validate orchestration pipelines before dispatching to physical hardware.
        </p>
      </header>

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-md border border-neutral-200 bg-white p-4 shadow-sm">
          <h2 className="text-lg font-medium">Instruments</h2>
          <p className="text-xs text-neutral-500">Select an instrument to inspect SOPs, guardrails, and custody alerts.</p>
          <ul className="mt-3 space-y-2">
            {(profiles ?? []).map((profile) => {
              const isActive = profile.equipment_id === selectedProfile?.equipment_id
              return (
                <li key={profile.equipment_id}>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedEquipmentId(profile.equipment_id)
                      setSelectedRunId(profile.active_run?.id ?? null)
                    }}
                    className={`w-full rounded-md border px-3 py-2 text-left ${
                      isActive ? 'border-blue-500 bg-blue-50' : 'border-neutral-200'
                    }`}
                  >
                    <div className="flex items-center justify-between text-sm font-medium">
                      <span>{profile.name}</span>
                      <span className="text-xs uppercase text-neutral-500">{profile.status}</span>
                    </div>
                    <div className="mt-1 text-xs text-neutral-500">
                      {profile.eq_type ? `${profile.eq_type} • ` : ''}Capabilities {profile.capabilities.length}
                    </div>
                    {profile.custody_alerts.length > 0 ? (
                      <div className="mt-2 rounded bg-amber-100 p-2 text-xs text-amber-900">
                        Custody alerts: {profile.custody_alerts.map((alert) => alert.reason).join(', ')}
                      </div>
                    ) : null}
                  </button>
                </li>
              )
            })}
          </ul>
        </div>

        <div className="rounded-md border border-neutral-200 bg-white p-4 shadow-sm">
          <h2 className="text-lg font-medium">Run Control</h2>
          {selectedProfile ? (
            <div className="space-y-3 text-sm">
              <div>
                <div className="font-semibold">Linked SOPs</div>
                <ul className="list-disc pl-5 text-xs text-neutral-600">
                  {selectedProfile.sops.map((sop) => (
                    <li key={sop.sop_id}>
                      {sop.title} v{sop.version} – {sop.status}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <div className="font-semibold">Simulation Scenario</div>
                <select
                  className="mt-1 w-full rounded border border-neutral-200 bg-white p-2 text-sm"
                  value={scenario}
                  onChange={(event) => setScenario(event.target.value)}
                >
                  {scenarios.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <button
                type="button"
                className="rounded bg-blue-600 px-4 py-2 text-sm font-semibold text-white disabled:bg-blue-300"
                disabled={simulationMutation.isPending || !normalizedEquipmentId}
                onClick={triggerSimulation}
              >
                {simulationMutation.isPending ? 'Running Simulation…' : 'Run Simulation'}
              </button>
              {simulationMutation.data ? (
                <p className="text-xs text-neutral-500">
                  Simulation completed with {simulationMutation.data.envelope.samples.length} telemetry checkpoints.
                </p>
              ) : null}
            </div>
          ) : (
            <p className="text-sm text-neutral-500">No instrument selected.</p>
          )}

          <div className="mt-4">
            <div className="text-sm font-semibold">Historical Runs</div>
            <ul className="mt-2 max-h-48 space-y-2 overflow-y-auto text-xs text-neutral-600">
              {(runs ?? []).map((run) => {
                const isActive = run.id === effectiveRunId
                return (
                  <li key={run.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedRunId(run.id)}
                      className={`w-full rounded border px-3 py-2 text-left ${
                        isActive ? 'border-green-500 bg-green-50' : 'border-neutral-200'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{run.status}</span>
                        <span>{new Date(run.updated_at).toLocaleTimeString()}</span>
                      </div>
                      <div className="mt-1 text-[11px] text-neutral-500">
                        Flags: {run.guardrail_flags.length ? run.guardrail_flags.join(', ') : 'none'}
                      </div>
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
        </div>

        <div className="rounded-md border border-neutral-200 bg-white p-4 shadow-sm">
          <h2 className="text-lg font-medium">Telemetry Timeline</h2>
          {events.length === 0 ? (
            <p className="text-sm text-neutral-500">Trigger a simulation or select a run to inspect telemetry checkpoints.</p>
          ) : (
            <ol className="mt-2 space-y-2 text-xs text-neutral-700">
              {events.map((event) => (
                <li key={`${event.event_type}-${event.sequence}`} className="rounded border border-neutral-200 p-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold">#{event.sequence} {event.event_type.toUpperCase()}</span>
                    <span>{new Date(event.recorded_at).toLocaleTimeString()}</span>
                  </div>
                  <pre className="mt-1 max-h-28 overflow-x-auto whitespace-pre-wrap rounded bg-neutral-50 p-2 text-[11px]">
                    {JSON.stringify(event.payload, null, 2)}
                  </pre>
                </li>
              ))}
            </ol>
          )}

          <div className="mt-4">
            <div className="text-sm font-semibold">Latest Telemetry Sample</div>
            {runTelemetry.length > 0 ? (
              <pre className="mt-2 max-h-32 overflow-x-auto whitespace-pre-wrap rounded bg-neutral-50 p-2 text-[11px]">
                {JSON.stringify(runTelemetry[runTelemetry.length - 1], null, 2)}
              </pre>
            ) : (
              <p className="text-xs text-neutral-500">No telemetry captured yet.</p>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}
