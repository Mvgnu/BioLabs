'use client'

import React from 'react'
import { Alert, Card, CardBody, CardHeader, EmptyState, LoadingState } from '../ui'
import type { CustodyLogEntry } from '../../types'

interface CustodyLedgerPanelProps {
  logs: CustodyLogEntry[] | undefined
  isLoading: boolean
  error?: Error | null
}

// purpose: render custody ledger history with guardrail context for governance reviews
// inputs: custody ledger entries filtered via governance API
// outputs: tabular timeline surfacing lineage gaps and guardrail alerts
// status: pilot
export default function CustodyLedgerPanel({
  logs,
  isLoading,
  error,
}: CustodyLedgerPanelProps) {
  if (isLoading) {
    return <LoadingState title="Loading custody ledger" />
  }

  if (error) {
    return (
      <Alert variant="error" title="Unable to load custody ledger">
        <p>{error.message}</p>
      </Alert>
    )
  }

  if (!logs || logs.length === 0) {
    return (
      <EmptyState
        title="No custody movements recorded"
        description="Create custody entries when samples move between compartments so governance dashboards can surface guardrail exceptions."
      />
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-col gap-1">
          <h2 className="text-lg font-semibold text-neutral-900">Custody ledger</h2>
          <p className="text-sm text-neutral-500">
            Recent custody movements with guardrail annotations. Review lineage gaps before authorising sample distribution.
          </p>
        </div>
      </CardHeader>
      <CardBody className="overflow-x-auto p-0">
        <table className="min-w-full divide-y divide-neutral-200 text-sm">
          <thead className="bg-neutral-50">
            <tr>
              <th scope="col" className="px-4 py-2 text-left font-semibold text-neutral-600">
                Timestamp
              </th>
              <th scope="col" className="px-4 py-2 text-left font-semibold text-neutral-600">
                Action
              </th>
              <th scope="col" className="px-4 py-2 text-left font-semibold text-neutral-600">
                Compartment
              </th>
              <th scope="col" className="px-4 py-2 text-left font-semibold text-neutral-600">
                Quantity
              </th>
              <th scope="col" className="px-4 py-2 text-left font-semibold text-neutral-600">
                Lineage
              </th>
              <th scope="col" className="px-4 py-2 text-left font-semibold text-neutral-600">
                Guardrails
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {logs.map((log) => (
              <tr key={log.id} className="bg-white">
                <td className="px-4 py-3 text-neutral-600">
                  {new Date(log.performed_at).toLocaleString()}
                </td>
                <td className="px-4 py-3 font-medium text-neutral-800">{log.custody_action}</td>
                <td className="px-4 py-3 text-neutral-600">
                  {log.compartment_id ?? 'Unassigned'}
                </td>
                <td className="px-4 py-3 text-neutral-600">
                  {log.quantity ?? 'n/a'} {log.quantity_units ?? ''}
                </td>
                <td className="px-4 py-3 text-neutral-600">
                  {log.asset_version_id ? (
                    <span className="font-mono text-xs">Asset {log.asset_version_id}</span>
                  ) : log.planner_session_id ? (
                    <span className="font-mono text-xs">Planner {log.planner_session_id}</span>
                  ) : (
                    <span className="text-red-600">Unlinked</span>
                  )}
                </td>
                <td className="px-4 py-3 text-neutral-600">
                  {log.guardrail_flags.length === 0 ? (
                    <span className="text-xs font-medium uppercase tracking-wide text-primary-600">Clear</span>
                  ) : (
                    <div className="flex flex-wrap gap-2">
                      {log.guardrail_flags.map((flag) => (
                        <span
                          key={flag}
                          className="inline-flex items-center rounded-full border border-red-300 bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-700"
                        >
                          {flag}
                        </span>
                      ))}
                    </div>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardBody>
    </Card>
  )
}
