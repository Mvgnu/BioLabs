'use client'

import React from 'react'
import { Alert, Card, CardBody, CardHeader, EmptyState, LoadingState } from '../ui'
import type { CustodyCompartmentNode, CustodyFreezerUnit } from '../../types'
import { cn } from '../../utils/cn'

interface CustodyFreezerMapProps {
  units: CustodyFreezerUnit[] | undefined
  isLoading: boolean
  error?: Error | null
}

// purpose: render freezer topology occupancy with guardrail overlays for governance operators
// inputs: custody freezer units with nested compartment analytics
// outputs: dashboard cards highlighting capacity utilisation and escalation flags
// status: pilot
export default function CustodyFreezerMap({
  units,
  isLoading,
  error,
}: CustodyFreezerMapProps) {
  if (isLoading) {
    return <LoadingState title="Loading freezer topology" />
  }

  if (error) {
    return (
      <Alert variant="error" title="Unable to load freezer topology">
        <p>{error.message}</p>
      </Alert>
    )
  }

  if (!units || units.length === 0) {
    return (
      <EmptyState
        title="No freezer units registered"
        description="Model freezer units and compartments to enable custody guardrail monitoring. Refer to docs/operations/custody_governance.md for setup guidance."
      />
    )
  }

  return (
    <div className="space-y-6">
      {units.map((unit) => (
        <Card key={unit.id} className="border-primary-100">
          <CardHeader>
            <div className="flex flex-col gap-1">
              <h2 className="text-lg font-semibold text-neutral-900">{unit.name}</h2>
              <p className="text-sm text-neutral-500">
                Status: <span className="font-medium text-neutral-700">{unit.status}</span>
                {unit.facility_code ? ` · Facility ${unit.facility_code}` : ''}
              </p>
              <p className="text-xs uppercase tracking-wide text-neutral-400">
                Guardrail policy synced with custody SOP
              </p>
            </div>
          </CardHeader>
          <CardBody className="space-y-4">
            {unit.compartments.length === 0 ? (
              <p className="text-sm text-neutral-500">
                No compartments defined. Add shelves, racks, or boxes to visualise custody occupancy.
              </p>
            ) : (
              <div className="space-y-3">
                {unit.compartments.map((node) => (
                  <CompartmentNode key={node.id} node={node} depth={0} />
                ))}
              </div>
            )}
          </CardBody>
        </Card>
      ))}
    </div>
  )
}

interface CompartmentNodeProps {
  node: CustodyCompartmentNode
  depth: number
}

function CompartmentNode({ node, depth }: CompartmentNodeProps) {
  const hasGuardrails = node.guardrail_flags.length > 0
  const severityClass = hasGuardrails
    ? 'border-red-200 bg-red-50'
    : 'border-neutral-200 bg-white'

  return (
    <div className={cn('rounded-lg border p-4 shadow-sm', severityClass)} style={{ marginLeft: depth * 16 }}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="text-sm font-semibold text-neutral-800">{node.label}</p>
          <p className="text-xs text-neutral-500">
            Occupancy {node.occupancy}
            {node.capacity != null ? ` / ${node.capacity}` : ''}
          </p>
        </div>
        {hasGuardrails ? (
          <div className="flex flex-wrap gap-2">
            {node.guardrail_flags.map((flag) => (
              <span
                key={flag}
                className="inline-flex items-center rounded-full border border-red-300 bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700"
              >
                {flag}
              </span>
            ))}
          </div>
        ) : (
          <span className="text-xs font-medium uppercase tracking-wide text-primary-600">
            Stable
          </span>
        )}
      </div>
      <div className="mt-2 text-xs text-neutral-500">
        {node.latest_activity_at ? (
          <span>Last movement {new Date(node.latest_activity_at).toLocaleString()}</span>
        ) : (
          <span>No custody history recorded</span>
        )}
      </div>
      {node.children.length > 0 && (
        <div className="mt-3 space-y-3">
          {node.children.map((child) => (
            <CompartmentNode key={child.id} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  )
}
