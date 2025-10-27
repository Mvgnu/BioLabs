"use client"

import React from 'react'
import Link from 'next/link'
import { Card, CardBody } from '../../components/ui'
import type {
  ExperimentScenario,
  ExperimentScenarioSnapshot,
} from '../../types'

interface ScenarioSummaryProps {
  scenario: ExperimentScenario
  snapshot?: ExperimentScenarioSnapshot | null
}

// purpose: render shareable summary cards for experiment preview scenarios
// status: pilot

export default function ScenarioSummary({ scenario, snapshot }: ScenarioSummaryProps) {
  const resourceCounts = {
    inventory: scenario.resource_overrides?.inventory_item_ids?.length ?? 0,
    bookings: scenario.resource_overrides?.booking_ids?.length ?? 0,
    equipment: scenario.resource_overrides?.equipment_ids?.length ?? 0,
  }

  const stageOverrides = scenario.stage_overrides
    .slice()
    .sort((a, b) => a.index - b.index)

  const deepLink = `/experiment-console/${scenario.execution_id}?scenario=${scenario.id}`

  return (
    <Card variant="outlined" className="shadow-sm" data-testid="scenario-summary-card">
      <CardBody className="space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-neutral-900">{scenario.name}</h3>
            {scenario.description && (
              <p className="mt-1 text-xs text-neutral-600">{scenario.description}</p>
            )}
          </div>
          <Link
            href={deepLink}
            className="text-xs font-medium text-indigo-600 hover:text-indigo-500"
          >
            Open scenario
          </Link>
        </div>

        <dl className="grid grid-cols-2 gap-3 text-xs text-neutral-600">
          <div>
            <dt className="font-semibold text-neutral-700">Snapshot</dt>
            <dd className="mt-1">
              {snapshot ? (
                <div className="space-y-1">
                  <p>
                    {snapshot.template_name ?? snapshot.template_key} · v{snapshot.version}
                  </p>
                  <p className="text-[11px] text-neutral-500">Captured {new Date(snapshot.captured_at).toLocaleString()}</p>
                </div>
              ) : (
                'Not available'
              )}
            </dd>
          </div>
          <div>
            <dt className="font-semibold text-neutral-700">Override footprint</dt>
            <dd className="mt-1 space-y-1">
              <p>Stage overrides: {stageOverrides.length}</p>
              <p>Inventory: {resourceCounts.inventory}</p>
              <p>Bookings: {resourceCounts.bookings}</p>
              <p>Equipment: {resourceCounts.equipment}</p>
            </dd>
          </div>
        </dl>

        {stageOverrides.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-xs font-semibold text-neutral-700">Stage adjustments</h4>
            <ul className="space-y-1">
              {stageOverrides.map((override) => (
                <li
                  key={`stage-override-${override.index}`}
                  className="rounded bg-indigo-50 px-2 py-1 text-xs text-indigo-700"
                >
                  Stage {override.index + 1} · SLA {override.sla_hours ?? '—'}h · Assignee{' '}
                  {override.assignee_id ?? '—'} · Delegate {override.delegate_id ?? '—'}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="flex flex-wrap gap-3 text-[11px] text-neutral-500">
          <span>Created {new Date(scenario.created_at).toLocaleString()}</span>
          <span>Updated {new Date(scenario.updated_at).toLocaleString()}</span>
          {scenario.cloned_from_id && <span>Cloned from {scenario.cloned_from_id}</span>}
        </div>
      </CardBody>
    </Card>
  )
}
