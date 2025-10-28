'use client'

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import type { QueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { governanceApi, mapGuardrailSimulationRecord } from '../api/governance'
import type {
  ExperimentExecutionSession,
  ExperimentExecutionSessionCreate,
  ExperimentPreviewRequest,
  ExperimentPreviewResponse,
  ExperimentRemediationRequest,
  ExperimentRemediationResponse,
  ExperimentStepStatusUpdate,
  ExperimentTimelinePage,
  GovernanceDecisionTimelinePage,
  GovernanceOverrideLineageAggregates,
  GovernanceOverrideReversalDetail,
  GovernanceOverrideReversalDiff,
  GovernanceOverrideReverseRequest,
  ExperimentScenario,
  ExperimentScenarioCloneRequest,
  ExperimentScenarioCreateRequest,
  ExperimentScenarioFolder,
  ExperimentScenarioFolderCreateRequest,
  ExperimentScenarioFolderUpdateRequest,
  ExperimentScenarioUpdateRequest,
  ExperimentScenarioWorkspace,
  ExecutionNarrativeExportHistory,
  ExecutionNarrativeExportRecord,
  ExecutionNarrativeExportCreate,
  ExecutionNarrativeApprovalRequest,
  ExecutionNarrativeDelegationRequest,
  ExecutionNarrativeStageResetRequest,
  GovernanceBaselineCollection,
  GovernanceBaselineVersion,
  BaselineSubmissionDraft,
  BaselineReviewDecision,
  BaselinePublishRequest,
  BaselineRollbackRequest,
} from '../types'

const sessionKey = (executionId: string | null) => [
  'experiment-console',
  'sessions',
  executionId,
]

const timelineKey = (
  executionId: string | null,
  filters?: { eventTypes?: string[] },
) => [
  'experiment-console',
  'timeline',
  executionId,
  filters?.eventTypes?.slice().sort().join(','),
]

const governanceTimelineKey = (
  executionId: string | null,
  pageSize: number,
) => ['experiment-console', 'governance-timeline', executionId, pageSize]

const exportsKey = (executionId: string | null) => [
  'experiment-console',
  'exports',
  executionId,
]

const scenarioWorkspaceKey = (executionId: string | null) => [
  'experiment-console',
  'scenarios',
  executionId,
]

const governanceAnalyticsKey = (executionId: string | null) => [
  'experiment-console',
  'governance-analytics',
  executionId ?? 'all',
]

const governanceBaselinesKey = (
  executionId: string | null,
  templateId: string | null,
) => [
  'experiment-console',
  'baselines',
  executionId ?? 'all',
  templateId ?? 'all',
]

export const invalidateTimelineQueries = (
  qc: QueryClient,
  executionId: string | null,
) => {
  if (!executionId) return
  qc.invalidateQueries({
    predicate: (query) =>
      Array.isArray(query.queryKey) &&
      query.queryKey[0] === 'experiment-console' &&
      query.queryKey[1] === 'timeline' &&
      query.queryKey[2] === executionId,
  })
}

export const invalidateGovernanceTimelineQueries = (
  qc: QueryClient,
  executionId: string | null,
) => {
  if (!executionId) return
  qc.invalidateQueries({
    predicate: (query) =>
      Array.isArray(query.queryKey) &&
      query.queryKey[0] === 'experiment-console' &&
      query.queryKey[1] === 'governance-timeline' &&
      query.queryKey[2] === executionId,
  })
}

export const invalidateGovernanceAnalyticsQueries = (
  qc: QueryClient,
  executionId: string | null,
) => {
  qc.invalidateQueries({
    predicate: (query) => {
      if (!Array.isArray(query.queryKey)) return false
      const [scope, keySegment] = query.queryKey
      if (scope === 'experiment-console' && keySegment === 'governance-analytics') {
        if (!executionId) {
          return true
        }
        const target = query.queryKey[2]
        return target === 'all' || target === executionId
      }
      if (scope === 'governance' && keySegment === 'reviewer-cadence') {
        if (!executionId) {
          return true
        }
        const target = query.queryKey[2]
        return target === 'all' || target === executionId
      }
      return false
    },
  })
}

const invalidateBaselineQueries = (qc: QueryClient) => {
  qc.invalidateQueries({
    predicate: (query) =>
      Array.isArray(query.queryKey) &&
      query.queryKey[0] === 'experiment-console' &&
      query.queryKey[1] === 'baselines',
  })
}

const coerceCount = (value: unknown) => {
  if (value === null || value === undefined) return 0
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

const normaliseReversalDiffs = (
  diffs: any,
): GovernanceOverrideReversalDiff[] => {
  if (!Array.isArray(diffs)) return []
  return diffs
    .map((item) => ({
      key: String(item?.key ?? ''),
      before: item?.before,
      after: item?.after,
    }))
    .filter((item) => item.key.length > 0)
}

const normaliseReversalDetail = (
  detail: any,
): GovernanceOverrideReversalDetail | null => {
  if (!detail || typeof detail !== 'object') {
    return null
  }
  const diffs = normaliseReversalDiffs(detail.diffs)
  const rawWindow = detail.cooldown_window_minutes
  const windowMinutes =
    rawWindow === null || rawWindow === undefined
      ? null
      : Number.isFinite(Number(rawWindow))
      ? Number(rawWindow)
      : null
  return {
    id: String(detail.id ?? ''),
    override_id: String(detail.override_id ?? ''),
    baseline_id: detail.baseline_id ?? null,
    actor: detail.actor ?? null,
    created_at: detail.created_at ?? null,
    cooldown_expires_at: detail.cooldown_expires_at ?? null,
    cooldown_window_minutes: windowMinutes,
    diffs,
    previous_detail: detail.previous_detail ?? {},
    current_detail: detail.current_detail ?? {},
    metadata: detail.metadata ?? {},
  }
}

// purpose: normalise lineage summary aggregates returned from governance timeline analytics
// inputs: raw lineage summary payload attached to timeline entry detail
// outputs: GovernanceOverrideLineageAggregates with numeric counts
// status: pilot
const normaliseLineageSummary = (
  summary: any,
): GovernanceOverrideLineageAggregates | null => {
  if (!summary || typeof summary !== 'object') {
    return null
  }
  const scenarios = Array.isArray(summary.scenarios)
    ? summary.scenarios.map((item: any) => ({
        scenario_id: item?.scenario_id ?? null,
        scenario_name: item?.scenario_name ?? null,
        folder_name: item?.folder_name ?? null,
        executed_count: coerceCount(item?.executed_count),
        reversed_count: coerceCount(item?.reversed_count),
        net_count: coerceCount(item?.net_count),
      }))
    : []
  const notebooks = Array.isArray(summary.notebooks)
    ? summary.notebooks.map((item: any) => ({
        notebook_entry_id: item?.notebook_entry_id ?? null,
        notebook_title: item?.notebook_title ?? null,
        execution_id: item?.execution_id ?? null,
        executed_count: coerceCount(item?.executed_count),
        reversed_count: coerceCount(item?.reversed_count),
        net_count: coerceCount(item?.net_count),
      }))
    : []
  return { scenarios, notebooks }
}

const mapGovernanceTimelineEntry = (entry: GovernanceDecisionTimelineEntry) => {
  const detail = { ...(entry.detail ?? {}) }
  const nestedDetail =
    detail.detail && typeof detail.detail === 'object'
      ? { ...detail.detail }
      : {}
  const reversalDetail =
    normaliseReversalDetail(detail.reversal_event) ||
    normaliseReversalDetail(nestedDetail.reversal_event)
  if (reversalDetail) {
    detail.reversal_event = reversalDetail
    nestedDetail.reversal_event = reversalDetail
  }
  if (nestedDetail.cooldown_expires_at) {
    nestedDetail.cooldown_expires_at = String(nestedDetail.cooldown_expires_at)
  }
  if (detail.cooldown_expires_at) {
    detail.cooldown_expires_at = String(detail.cooldown_expires_at)
  }
  if (nestedDetail.cooldown_window_minutes !== undefined) {
    const parsedWindow = Number(nestedDetail.cooldown_window_minutes)
    nestedDetail.cooldown_window_minutes = Number.isFinite(parsedWindow)
      ? parsedWindow
      : null
  }
  if (detail.cooldown_window_minutes !== undefined) {
    const parsedWindow = Number(detail.cooldown_window_minutes)
    detail.cooldown_window_minutes = Number.isFinite(parsedWindow)
      ? parsedWindow
      : null
  }
  if (detail.lineage_summary) {
    const summary = normaliseLineageSummary(detail.lineage_summary)
    if (summary) {
      detail.lineage_summary = summary
    } else {
      delete detail.lineage_summary
    }
  }
  if (Object.keys(nestedDetail).length > 0) {
    detail.detail = nestedDetail
  }
  return { ...entry, detail }
}

export const useExperimentSession = (executionId: string | null) => {
  return useQuery({
    queryKey: sessionKey(executionId),
    enabled: Boolean(executionId),
    queryFn: async () => {
      const resp = await api.get(`/api/experiment-console/sessions/${executionId}`)
      return resp.data as ExperimentExecutionSession
    },
  })
}

export const useCreateExperimentSession = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload: ExperimentExecutionSessionCreate) => {
      const resp = await api.post('/api/experiment-console/sessions', payload)
      return resp.data as ExperimentExecutionSession
    },
    onSuccess: (data) => {
      qc.setQueryData(sessionKey(data.execution.id), data)
    },
  })
}

export const useUpdateExperimentStep = (executionId: string | null) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: { stepIndex: number; update: ExperimentStepStatusUpdate }) => {
      if (!executionId) {
        throw new Error('Execution id required for step updates')
      }
      const resp = await api.post(
        `/api/experiment-console/sessions/${executionId}/steps/${vars.stepIndex}`,
        vars.update,
      )
      return resp.data as ExperimentExecutionSession
    },
    onSuccess: (data) => {
      qc.setQueryData(sessionKey(executionId), data)
    },
  })
}

export const useAdvanceExperimentStep = (executionId: string | null) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: { stepIndex: number }) => {
      if (!executionId) {
        throw new Error('Execution id required for orchestration advance')
      }
      const resp = await api.post(
        `/api/experiment-console/sessions/${executionId}/steps/${vars.stepIndex}/advance`,
        {},
      )
      return resp.data as ExperimentExecutionSession
    },
    onSuccess: (data) => {
      qc.setQueryData(sessionKey(executionId), data)
    },
  })
}

export const useRemediateExperimentStep = (executionId: string | null) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: {
      stepIndex: number
      request?: ExperimentRemediationRequest
    }) => {
      if (!executionId) {
        throw new Error('Execution id required for remediation')
      }
      const resp = await api.post(
        `/api/experiment-console/sessions/${executionId}/steps/${vars.stepIndex}/remediate`,
        vars.request ?? {},
      )
      return resp.data as ExperimentRemediationResponse
    },
    onSuccess: (data) => {
      qc.setQueryData(sessionKey(executionId), data.session)
    },
  })
}

export const useExecutionTimeline = (
  executionId: string | null,
  filters?: { eventTypes?: string[]; pageSize?: number },
) => {
  const pageSize = Math.min(Math.max(filters?.pageSize ?? 50, 1), 200)
  return useInfiniteQuery({
    queryKey: timelineKey(executionId, filters),
    enabled: Boolean(executionId),
    queryFn: async ({ pageParam }): Promise<ExperimentTimelinePage> => {
      if (!executionId) {
        throw new Error('Execution id required for timeline queries')
      }
      const params: Record<string, any> = { limit: pageSize }
      if (pageParam) {
        params.cursor = pageParam
      }
      if (filters?.eventTypes?.length) {
        params.event_types = filters.eventTypes.join(',')
      }
      const resp = await api.get(
        `/api/experiment-console/sessions/${executionId}/timeline`,
        { params },
      )
      return resp.data as ExperimentTimelinePage
    },
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  })
}

export const useGovernanceDecisionTimeline = (
  executionId: string | null,
  options?: { pageSize?: number },
) => {
  const pageSize = Math.min(Math.max(options?.pageSize ?? 20, 1), 200)
  return useInfiniteQuery({
    queryKey: governanceTimelineKey(executionId, pageSize),
    enabled: Boolean(executionId),
    queryFn: async ({ pageParam }): Promise<GovernanceDecisionTimelinePage> => {
      if (!executionId) {
        throw new Error('Execution id required for governance timeline queries')
      }
      const params: Record<string, any> = { limit: pageSize, execution_id: executionId }
      if (pageParam) {
        params.cursor = pageParam
      }
      const resp = await api.get('/api/experiment-console/governance/timeline', {
        params,
      })
      const page = resp.data as GovernanceDecisionTimelinePage
      return {
        ...page,
        entries: page.entries.map((entry) => mapGovernanceTimelineEntry(entry)),
      }
    },
    getNextPageParam: (lastPage) => lastPage.next_cursor ?? undefined,
  })
}

export const useReverseGovernanceOverride = (executionId: string | null) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: {
      recommendationId: string
      payload: GovernanceOverrideReverseRequest
    }) => {
      const response = await governanceApi.reverseOverride(
        vars.recommendationId,
        vars.payload,
      )
      return response
    },
    onSuccess: () => {
      invalidateGovernanceTimelineQueries(qc, executionId)
      invalidateGovernanceAnalyticsQueries(qc, executionId)
    },
  })
}

export const useExecutionNarrativeExports = (executionId: string | null) => {
  return useQuery({
    queryKey: exportsKey(executionId),
    enabled: Boolean(executionId),
    queryFn: async () => {
      if (!executionId) {
        throw new Error('Execution id required for export history queries')
      }
      const resp = await api.get(
        `/api/experiment-console/sessions/${executionId}/exports/narrative`,
      )
      const history = resp.data as ExecutionNarrativeExportHistory
      return {
        ...history,
        exports: history.exports.map((exportRecord) => ({
          ...exportRecord,
          guardrail_simulation: exportRecord.guardrail_simulation
            ? mapGuardrailSimulationRecord(exportRecord.guardrail_simulation)
            : null,
        })),
      }
    },
  })
}

export const useGovernanceAnalytics = (
  executionId: string | null,
  limit = 50,
) => {
  return useQuery({
    queryKey: governanceAnalyticsKey(executionId),
    queryFn: async () => {
      const params: Record<string, any> = { limit }
      if (executionId) {
        params.execution_id = executionId
      }
      return governanceApi.getAnalytics(params)
    },
  })
}

export const useGovernanceBaselines = (
  executionId: string | null,
  templateId: string | null,
) => {
  return useQuery<GovernanceBaselineVersion[]>({
    queryKey: governanceBaselinesKey(executionId, templateId),
    enabled: Boolean(executionId || templateId),
    queryFn: async () => {
      const response: GovernanceBaselineCollection =
        await governanceApi.listBaselines({
          execution_id: executionId ?? undefined,
          template_id: templateId ?? undefined,
        })
      return response.items
    },
  })
}

type SubmitBaselinePayload = Omit<BaselineSubmissionDraft, 'execution_id'> & {
  execution_id?: string
}

export const useSubmitBaseline = (
  executionId: string | null,
  templateId: string | null,
) => {
  const qc = useQueryClient()
  const key = governanceBaselinesKey(executionId, templateId)
  return useMutation({
    mutationFn: async (payload: SubmitBaselinePayload) => {
      const execution = payload.execution_id ?? executionId
      if (!execution) {
        throw new Error('Execution id required for baseline submission')
      }
      const submission: BaselineSubmissionDraft = {
        ...payload,
        execution_id: execution,
        labels: payload.labels ?? [],
        reviewer_ids: payload.reviewer_ids ?? [],
      }
      return governanceApi.submitBaseline(submission)
    },
    onMutate: async (payload) => {
      await qc.cancelQueries({ queryKey: key })
      const previous = qc.getQueryData<GovernanceBaselineVersion[] | undefined>(key)
      const targetExecution = payload.execution_id ?? executionId
      if (!targetExecution) {
        return { previous, optimisticId: undefined }
      }
      const now = new Date().toISOString()
      const optimistic: GovernanceBaselineVersion = {
        id: `optimistic-${Date.now()}`,
        execution_id: targetExecution,
        template_id: templateId,
        team_id: null,
        name: payload.name,
        description: payload.description ?? null,
        status: 'submitted',
        labels: payload.labels ?? [],
        reviewer_ids: payload.reviewer_ids ?? [],
        version_number: null,
        is_current: false,
        submitted_by_id: 'pending',
        submitted_at: now,
        reviewed_by_id: null,
        reviewed_at: null,
        review_notes: null,
        published_by_id: null,
        published_at: null,
        publish_notes: null,
        rollback_of_id: null,
        rolled_back_by_id: null,
        rolled_back_at: null,
        rollback_notes: null,
        created_at: now,
        updated_at: now,
        events: [],
      }
      qc.setQueryData<GovernanceBaselineVersion[]>(key, (existing = []) => [
        optimistic,
        ...existing,
      ])
      return { previous, optimisticId: optimistic.id }
    },
    onError: (_error, _vars, ctx) => {
      if (ctx?.previous) {
        qc.setQueryData(key, ctx.previous)
      }
    },
    onSuccess: (data, _vars, ctx) => {
      qc.setQueryData<GovernanceBaselineVersion[]>(key, (existing = []) => {
        const filtered = existing.filter((item) => item.id !== ctx?.optimisticId)
        return [data, ...filtered]
      })
      invalidateBaselineQueries(qc)
    },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: key })
    },
  })
}

export const useReviewBaseline = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: {
      baselineId: string
      payload: BaselineReviewDecision
    }) => governanceApi.reviewBaseline(vars.baselineId, vars.payload),
    onSuccess: (data) => {
      invalidateBaselineQueries(qc)
      return data
    },
  })
}

export const usePublishBaseline = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: {
      baselineId: string
      payload: BaselinePublishRequest
    }) => governanceApi.publishBaseline(vars.baselineId, vars.payload),
    onSuccess: (data) => {
      invalidateBaselineQueries(qc)
      return data
    },
  })
}

export const useRollbackBaseline = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: {
      baselineId: string
      payload: BaselineRollbackRequest
    }) => governanceApi.rollbackBaseline(vars.baselineId, vars.payload),
    onSuccess: (data) => {
      invalidateBaselineQueries(qc)
      return data
    },
  })
}

export const useCreateNarrativeExport = (executionId: string | null) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (
      payload: ExecutionNarrativeExportCreate = {},
    ): Promise<ExecutionNarrativeExportRecord> => {
      if (!executionId) {
        throw new Error('Execution id required for narrative export creation')
      }
      const resp = await api.post(
        `/api/experiment-console/sessions/${executionId}/exports/narrative`,
        payload,
      )
      return resp.data as ExecutionNarrativeExportRecord
    },
    onSuccess: (data) => {
      qc.setQueryData<ExecutionNarrativeExportHistory | undefined>(
        exportsKey(executionId),
        (current) => {
          if (!current) {
            return { exports: [data] }
          }
          const deduped = current.exports.filter((entry) => entry.id !== data.id)
          return { exports: [data, ...deduped] }
        },
      )
      invalidateTimelineQueries(qc, executionId)
    },
  })
}

export const useExperimentPreview = (executionId: string | null) => {
  return useMutation({
    mutationFn: async (
      payload: ExperimentPreviewRequest,
    ): Promise<ExperimentPreviewResponse> => {
      if (!executionId) {
        throw new Error('Execution id required for governance preview')
      }
      const resp = await api.post(
        `/api/experiments/${executionId}/preview`,
        payload,
      )
      return resp.data as ExperimentPreviewResponse
    },
  })
}

export const useScenarioWorkspace = (executionId: string | null) => {
  return useQuery({
    queryKey: scenarioWorkspaceKey(executionId),
    enabled: Boolean(executionId),
    queryFn: async () => {
      if (!executionId) {
        throw new Error('Execution id required for scenario workspace queries')
      }
      const resp = await api.get(`/api/experiments/${executionId}/scenarios`)
      return resp.data as ExperimentScenarioWorkspace
    },
  })
}

export const useCreateScenario = (executionId: string | null) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (
      payload: ExperimentScenarioCreateRequest,
    ): Promise<ExperimentScenario> => {
      if (!executionId) {
        throw new Error('Execution id required for scenario creation')
      }
      const resp = await api.post(
        `/api/experiments/${executionId}/scenarios`,
        payload,
      )
      return resp.data as ExperimentScenario
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: scenarioWorkspaceKey(executionId) })
    },
  })
}

export const useCreateScenarioFolder = (executionId: string | null) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (
      payload: ExperimentScenarioFolderCreateRequest,
    ): Promise<ExperimentScenarioFolder> => {
      if (!executionId) {
        throw new Error('Execution id required for folder creation')
      }
      const resp = await api.post(
        `/api/experiments/${executionId}/scenario-folders`,
        payload,
      )
      return resp.data as ExperimentScenarioFolder
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: scenarioWorkspaceKey(executionId) })
    },
  })
}

export const useUpdateScenarioFolder = (executionId: string | null) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: {
      folderId: string
      payload: ExperimentScenarioFolderUpdateRequest
    }): Promise<ExperimentScenarioFolder> => {
      if (!executionId) {
        throw new Error('Execution id required for folder updates')
      }
      const resp = await api.patch(
        `/api/experiments/${executionId}/scenario-folders/${vars.folderId}`,
        vars.payload,
      )
      return resp.data as ExperimentScenarioFolder
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: scenarioWorkspaceKey(executionId) })
    },
  })
}

export const useUpdateScenario = (executionId: string | null) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: {
      scenarioId: string
      payload: ExperimentScenarioUpdateRequest
    }): Promise<ExperimentScenario> => {
      if (!executionId) {
        throw new Error('Execution id required for scenario updates')
      }
      const resp = await api.put(
        `/api/experiments/${executionId}/scenarios/${vars.scenarioId}`,
        vars.payload,
      )
      return resp.data as ExperimentScenario
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: scenarioWorkspaceKey(executionId) })
    },
  })
}

export const useCloneScenario = (executionId: string | null) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: {
      scenarioId: string
      payload: ExperimentScenarioCloneRequest
    }): Promise<ExperimentScenario> => {
      if (!executionId) {
        throw new Error('Execution id required for scenario cloning')
      }
      const resp = await api.post(
        `/api/experiments/${executionId}/scenarios/${vars.scenarioId}/clone`,
        vars.payload,
      )
      return resp.data as ExperimentScenario
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: scenarioWorkspaceKey(executionId) })
    },
  })
}

export const useDeleteScenario = (executionId: string | null) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (scenarioId: string) => {
      if (!executionId) {
        throw new Error('Execution id required for scenario deletion')
      }
      await api.delete(
        `/api/experiments/${executionId}/scenarios/${scenarioId}`,
      )
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: scenarioWorkspaceKey(executionId) })
    },
  })
}

export const useApproveNarrativeExport = (executionId: string | null) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: {
      exportId: string
      approval: ExecutionNarrativeApprovalRequest
    }): Promise<ExecutionNarrativeExportRecord> => {
      if (!executionId) {
        throw new Error('Execution id required for narrative approval')
      }
      const resp = await api.post(
        `/api/experiment-console/sessions/${executionId}/exports/narrative/${vars.exportId}/approve`,
        vars.approval,
      )
      return resp.data as ExecutionNarrativeExportRecord
    },
    onSuccess: (data) => {
      qc.setQueryData<ExecutionNarrativeExportHistory | undefined>(
        exportsKey(executionId),
        (current) => {
          if (!current) {
            return { exports: [data] }
          }
          const remaining = current.exports.filter((entry) => entry.id !== data.id)
          return { exports: [data, ...remaining] }
        },
      )
      invalidateTimelineQueries(qc, executionId)
    },
  })
}

export const useDelegateNarrativeApprovalStage = (executionId: string | null) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: {
      exportId: string
      stageId: string
      delegation: ExecutionNarrativeDelegationRequest
    }): Promise<ExecutionNarrativeExportRecord> => {
      if (!executionId) {
        throw new Error('Execution id required for stage delegation')
      }
      const resp = await api.post(
        `/api/experiment-console/sessions/${executionId}/exports/narrative/${vars.exportId}/stages/${vars.stageId}/delegate`,
        vars.delegation,
      )
      return resp.data as ExecutionNarrativeExportRecord
    },
    onSuccess: (data) => {
      qc.setQueryData<ExecutionNarrativeExportHistory | undefined>(
        exportsKey(executionId),
        (current) => {
          if (!current) {
            return { exports: [data] }
          }
          const remaining = current.exports.filter((entry) => entry.id !== data.id)
          return { exports: [data, ...remaining] }
        },
      )
      invalidateTimelineQueries(qc, executionId)
    },
  })
}

export const useResetNarrativeApprovalStage = (executionId: string | null) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: {
      exportId: string
      stageId: string
      reset: ExecutionNarrativeStageResetRequest
    }): Promise<ExecutionNarrativeExportRecord> => {
      if (!executionId) {
        throw new Error('Execution id required for stage reset')
      }
      const resp = await api.post(
        `/api/experiment-console/sessions/${executionId}/exports/narrative/${vars.exportId}/stages/${vars.stageId}/reset`,
        vars.reset,
      )
      return resp.data as ExecutionNarrativeExportRecord
    },
    onSuccess: (data) => {
      qc.setQueryData<ExecutionNarrativeExportHistory | undefined>(
        exportsKey(executionId),
        (current) => {
          if (!current) {
            return { exports: [data] }
          }
          const remaining = current.exports.filter((entry) => entry.id !== data.id)
          return { exports: [data, ...remaining] }
        },
      )
      invalidateTimelineQueries(qc, executionId)
    },
  })
}
