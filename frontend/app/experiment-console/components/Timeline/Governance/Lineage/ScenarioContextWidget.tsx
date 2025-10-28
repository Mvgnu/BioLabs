'use client'

import React from 'react'

import type { GovernanceOverrideLineageContext } from '../../../../../types'

export interface ScenarioContextWidgetProps {
  lineage: GovernanceOverrideLineageContext
}

const formatTimestamp = (value?: string | null) => {
  if (!value) return null
  try {
    return new Intl.DateTimeFormat('en', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(value))
  } catch (error) {
    return value
  }
}

// biolab: purpose=render override lineage snapshot;status=pilot;depends_on=GovernanceDecisionTimelineEntry
const ScenarioContextWidget = ({ lineage }: ScenarioContextWidgetProps) => {
  const scenario = lineage.scenario
  const notebook = lineage.notebook_entry
  const capturedLabel = formatTimestamp(lineage.captured_at)
  const capturedBy = lineage.captured_by?.name || lineage.captured_by?.email || null

  if (!scenario && !notebook) {
    return null
  }

  return (
    <section
      className="rounded-md border border-indigo-100 bg-indigo-50 p-3"
      data-biolab-widget="governance-override-lineage"
    >
      <header className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-indigo-700">Lineage Context</p>
        {capturedLabel && (
          <span className="text-[11px] text-indigo-600">
            {capturedBy ? `${capturedBy} • ${capturedLabel}` : capturedLabel}
          </span>
        )}
      </header>
      <dl className="mt-2 space-y-2 text-sm text-indigo-900">
        {scenario && (
          <div>
            <dt className="font-medium text-indigo-700">Scenario</dt>
            <dd>
              {scenario.name ?? scenario.id}
              {scenario.folder_name && (
                <span className="block text-xs text-indigo-600">Folder: {scenario.folder_name}</span>
              )}
            </dd>
          </div>
        )}
        {notebook && (
          <div>
            <dt className="font-medium text-indigo-700">Notebook</dt>
            <dd>
              {notebook.title ?? notebook.id}
              {notebook.execution_id && (
                <span className="block text-xs text-indigo-600">Execution: {notebook.execution_id}</span>
              )}
            </dd>
          </div>
        )}
        {lineage.metadata && Object.keys(lineage.metadata).length > 0 && (
          <div>
            <dt className="font-medium text-indigo-700">Metadata</dt>
            <dd className="text-xs text-indigo-600">
              {JSON.stringify(lineage.metadata)}
            </dd>
          </div>
        )}
      </dl>
    </section>
  )
}

export default ScenarioContextWidget
