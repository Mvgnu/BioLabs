'use client'

import React, { useEffect, useMemo, useState } from 'react'
import {
  useGovernanceBaselines,
  usePublishBaseline,
  useReviewBaseline,
  useRollbackBaseline,
  useSubmitBaseline,
} from '../../../hooks/useExperimentConsole'
import type { BaselineLifecycleLabel, GovernanceBaselineVersion } from '../../../types'
import BaselineReviewerQueue from './BaselineReviewerQueue'
import BaselineSubmissionForm from './BaselineSubmissionForm'
import BaselineTimeline from './BaselineTimeline'

interface BaselinesPanelProps {
  executionId: string
  templateId?: string | null
  templateName?: string | null
  canManage: boolean
  currentUserId?: string | null
}

// purpose: orchestrate governance baseline lifecycle interactions inside experiment console
// inputs: execution context identifiers, RBAC flags, react-query mutation hooks
// outputs: cohesive scientist and reviewer experience for submissions and approvals
// status: pilot
export default function BaselinesPanel({
  executionId,
  templateId = null,
  templateName,
  canManage,
  currentUserId,
}: BaselinesPanelProps) {
  const baselineQuery = useGovernanceBaselines(executionId, templateId)
  const submissionMutation = useSubmitBaseline(executionId, templateId)
  const reviewMutation = useReviewBaseline()
  const publishMutation = usePublishBaseline()
  const rollbackMutation = useRollbackBaseline()

  const parseError = (error: unknown) => {
    if (!error) return null
    if (error instanceof Error) return error.message
    if (typeof error === 'string') return error
    if (typeof error === 'object' && 'message' in (error as any)) {
      return String((error as any).message)
    }
    return 'Unexpected error encountered.'
  }

  const [selectedId, setSelectedId] = useState<string | null>(null)

  const baselines = baselineQuery.data ?? []

  useEffect(() => {
    if (!baselines.length) {
      setSelectedId(null)
      return
    }
    if (selectedId && baselines.some((baseline) => baseline.id === selectedId)) {
      return
    }
    setSelectedId(baselines[0]?.id ?? null)
  }, [baselines, selectedId])

  const activeBaseline = useMemo<GovernanceBaselineVersion | null>(() => {
    if (!selectedId) return baselines[0] ?? null
    return baselines.find((baseline) => baseline.id === selectedId) ?? baselines[0] ?? null
  }, [baselines, selectedId])

  const handleSubmission = (payload: {
    name: string
    description?: string | null
    reviewerIds: string[]
    labels: BaselineLifecycleLabel[]
  }) => {
    if (!canManage) {
      return
    }
    submissionMutation.mutate({
      execution_id: executionId,
      name: payload.name,
      description: payload.description,
      reviewer_ids: payload.reviewerIds,
      labels: payload.labels,
    })
  }

  const handleReview = (baselineId: string, payload: { decision: 'approve' | 'reject'; notes?: string }) => {
    reviewMutation.mutate({ baselineId, payload })
  }

  const handlePublish = (baselineId: string, notes?: string | null) => {
    publishMutation.mutate({ baselineId, payload: { notes: notes ?? undefined } })
  }

  const handleRollback = (baselineId: string, reason: string) => {
    rollbackMutation.mutate({ baselineId, payload: { reason } })
  }

  return (
    <section className="space-y-6" data-testid="baseline-governance-panel">
      <header className="space-y-2">
        <h2 className="text-2xl font-semibold text-neutral-900">Baseline governance</h2>
        <p className="text-sm text-neutral-600 max-w-4xl">
          Operationalize preview learnings into versioned governance baselines. Scientists submit proposals, reviewers adjudicate,
          and administrators publish or roll back using this workspace. All activity mirrors backend lifecycle state for audits.
        </p>
      </header>

      {!canManage && (
        <div className="border border-amber-200 bg-amber-50 text-amber-700 text-sm rounded-md p-3">
          You have view-only access to governance baselines for this execution. Contact an administrator to request reviewer or
          publisher permissions.
        </div>
      )}

      <BaselineSubmissionForm
        executionId={executionId}
        templateName={templateName}
        onSubmit={handleSubmission}
        submitting={submissionMutation.isPending}
        disabled={!canManage}
        errorMessage={
          canManage && submissionMutation.isError
            ? parseError(submissionMutation.error)
            : null
        }
      />

      <div className="grid gap-6 lg:grid-cols-2 items-start">
        <BaselineReviewerQueue
          baselines={baselines}
          selectedId={activeBaseline?.id ?? null}
          onSelect={setSelectedId}
          onReview={handleReview}
          onPublish={handlePublish}
          onRollback={handleRollback}
          canManage={canManage}
          currentUserId={currentUserId}
        />
        <div className="space-y-4">
          {baselineQuery.isLoading && (
            <div className="border border-neutral-200 rounded-lg bg-white shadow-sm p-4 text-sm text-neutral-500">
              Loading baseline lifecycle history…
            </div>
          )}
          {baselineQuery.isError && (
            <div className="border border-rose-200 rounded-lg bg-rose-50 text-rose-700 text-sm p-4">
              Unable to load governance baselines for this execution.
            </div>
          )}
          {!baselineQuery.isLoading && !baselineQuery.isError && activeBaseline && (
            <BaselineTimeline events={activeBaseline.events ?? []} baselineName={activeBaseline.name} />
          )}
        </div>
      </div>
    </section>
  )
}
