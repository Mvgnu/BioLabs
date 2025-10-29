import api from './client'
import type {
  BaselinePublishRequest,
  BaselineReviewDecision,
  BaselineRollbackRequest,
  BaselineSubmissionDraft,
  GovernanceBaselineCollection,
  GovernanceBaselineVersion,
  GovernanceTemplate,
  GovernanceTemplateAssignment,
  GovernanceTemplateDraft,
  GovernanceAnalyticsReport,
  GovernanceAnalyticsPreviewSummary,
  GovernanceReviewerCadenceSummary,
  GovernanceAnalyticsLatencyBand,
  GovernanceReviewerCadenceReport,
  GovernanceReviewerCadenceTotals,
  GovernanceReviewerLoadBandCounts,
  GovernanceScenarioOverrideAggregate,
  GovernanceNotebookOverrideAggregate,
  GovernanceOverrideLineageAggregates,
  GovernanceOverrideActionRecord,
  GovernanceOverrideActionRequest,
  GovernanceOverrideReverseRequest,
  GovernanceOverrideRecommendationReport,
  GovernanceGuardrailSimulationRecord,
  GovernanceAnalyticsMeta,
  GovernanceOverdueStageSummary,
  GovernanceOverdueStageSample,
  GovernanceOverdueStageTrendBucket,
  GovernanceStageMetrics,
  GovernanceStageDetailMetrics,
  GovernanceGuardrailHealthReport,
  GovernanceGuardrailHealthTotals,
  GovernanceGuardrailQueueEntry,
  CustodyFreezerUnit,
  CustodyLogEntry,
  CustodyLogCreate,
} from '../types'

export interface GovernanceTemplateListParams {
  includeAll?: boolean
}

export interface GovernanceAssignmentCreate {
  template_id: string
  team_id?: string | null
  protocol_template_id?: string | null
  metadata?: Record<string, any>
}

// purpose: governance API gateway for admin workspace
// inputs: axios client, governance identifiers
// outputs: typed REST helpers for React hooks
// status: experimental
export const governanceApi = {
  async listTemplates(params?: GovernanceTemplateListParams) {
    const response = await api.get<GovernanceTemplate[]>(
      '/api/governance/templates',
      {
        params: params?.includeAll ? { include_all: params.includeAll } : undefined,
      }
    )
    return response.data
  },
  async getTemplate(templateId: string) {
    const response = await api.get<GovernanceTemplate>(
      `/api/governance/templates/${templateId}`
    )
    return response.data
  },
  async createTemplate(payload: GovernanceTemplateDraft) {
    const response = await api.post<GovernanceTemplate>(
      '/api/governance/templates',
      {
        ...payload,
        stage_blueprint: payload.stage_blueprint.map((stage) => ({
          name: stage.name,
          required_role: stage.required_role,
          sla_hours: stage.sla_hours,
          metadata: stage.metadata ?? {},
        })),
        permitted_roles: payload.permitted_roles ?? [],
        publish: Boolean(payload.publish),
      }
    )
    return response.data
  },
  async listAssignments(templateId: string) {
    const response = await api.get<GovernanceTemplateAssignment[]>(
      `/api/governance/templates/${templateId}/assignments`
    )
    return response.data
  },
  async createAssignment(payload: GovernanceAssignmentCreate) {
    const response = await api.post<GovernanceTemplateAssignment>(
      `/api/governance/templates/${payload.template_id}/assignments`,
      {
        template_id: payload.template_id,
        team_id: payload.team_id,
        protocol_template_id: payload.protocol_template_id,
        metadata: payload.metadata ?? {},
      }
    )
    return response.data
  },
  async deleteAssignment(assignmentId: string) {
    await api.delete(`/api/governance/assignments/${assignmentId}`)
    return assignmentId
  },
  async listBaselines(params?: { execution_id?: string; template_id?: string }) {
    const response = await api.get<GovernanceBaselineCollection>(
      '/api/governance/baselines',
      {
        params,
      },
    )
    return response.data
  },
  async getAnalytics(params?: { execution_id?: string; limit?: number | null }) {
    const response = await api.get<GovernanceAnalyticsReport>(
      '/api/governance/analytics',
      { params: { ...params, view: 'full' } },
    )
    return mapGovernanceAnalyticsReport(response.data)
  },
  async getReviewerCadence(params?: { execution_id?: string; limit?: number | null }) {
    const response = await api.get<GovernanceReviewerCadenceReport>(
      '/api/governance/analytics',
      { params: { ...params, view: 'reviewer' } },
    )
    return mapGovernanceReviewerCadenceReport(response.data)
  },
  async getGuardrailHealth(params?: { execution_id?: string; limit?: number | null }) {
    const response = await api.get<GovernanceGuardrailHealthReport>(
      '/api/governance/guardrails/health',
      {
        params: {
          execution_id: params?.execution_id ?? undefined,
          limit: params?.limit ?? undefined,
        },
      },
    )
    return mapGovernanceGuardrailHealthReport(response.data)
  },
  async getOverrideRecommendations(params?: { execution_id?: string; limit?: number | null }) {
    const response = await api.get<GovernanceOverrideRecommendationReport>(
      '/api/governance/recommendations/override',
      { params },
    )
    return response.data
  },
  async listGuardrailSimulations(params: { executionId: string; limit?: number | null }) {
    const response = await api.get<GovernanceGuardrailSimulationRecord[]>(
      '/api/governance/guardrails/simulations',
      {
        params: {
          execution_id: params.executionId,
          limit: params.limit ?? undefined,
        },
      },
    )
    return response.data.map((record) => mapGuardrailSimulationRecord(record))
  },
  async getGuardrailSimulation(simulationId: string) {
    const response = await api.get<GovernanceGuardrailSimulationRecord>(
      `/api/governance/guardrails/simulations/${simulationId}`,
    )
    return mapGuardrailSimulationRecord(response.data)
  },
  async acceptOverride(recommendationId: string, payload: GovernanceOverrideActionRequest) {
    const response = await api.post<GovernanceOverrideActionRecord>(
      `/api/governance/recommendations/override/${recommendationId}/accept`,
      payload,
    )
    return response.data
  },
  async declineOverride(recommendationId: string, payload: GovernanceOverrideActionRequest) {
    const response = await api.post<GovernanceOverrideActionRecord>(
      `/api/governance/recommendations/override/${recommendationId}/decline`,
      payload,
    )
    return response.data
  },
  async executeOverride(recommendationId: string, payload: GovernanceOverrideActionRequest) {
    const response = await api.post<GovernanceOverrideActionRecord>(
      `/api/governance/recommendations/override/${recommendationId}/execute`,
      payload,
    )
    return response.data
  },
  async reverseOverride(
    recommendationId: string,
    payload: GovernanceOverrideReverseRequest,
  ) {
    const response = await api.post<GovernanceOverrideActionRecord>(
      `/api/governance/recommendations/override/${recommendationId}/reverse`,
      payload,
    )
    return response.data
  },
  async getBaseline(baselineId: string) {
    const response = await api.get<GovernanceBaselineVersion>(
      `/api/governance/baselines/${baselineId}`,
    )
    return response.data
  },
  async submitBaseline(payload: BaselineSubmissionDraft) {
    const response = await api.post<GovernanceBaselineVersion>(
      '/api/governance/baselines/submissions',
      payload,
    )
    return response.data
  },
  async reviewBaseline(
    baselineId: string,
    payload: BaselineReviewDecision,
  ) {
    const response = await api.post<GovernanceBaselineVersion>(
      `/api/governance/baselines/${baselineId}/review`,
      payload,
    )
    return response.data
  },
  async publishBaseline(
    baselineId: string,
    payload: BaselinePublishRequest,
  ) {
    const response = await api.post<GovernanceBaselineVersion>(
      `/api/governance/baselines/${baselineId}/publish`,
      payload,
    )
    return response.data
  },
  async rollbackBaseline(
    baselineId: string,
    payload: BaselineRollbackRequest,
  ) {
    const response = await api.post<GovernanceBaselineVersion>(
      `/api/governance/baselines/${baselineId}/rollback`,
      payload,
    )
    return response.data
  },
  async getCustodyFreezers(params?: { team_id?: string | null }) {
    const response = await api.get<CustodyFreezerUnit[]>(
      '/api/governance/custody/freezers',
      {
        params: {
          team_id: params?.team_id ?? undefined,
        },
      },
    )
    return response.data
  },
  async listCustodyLogs(params?: {
    asset_id?: string | null
    asset_version_id?: string | null
    planner_session_id?: string | null
    compartment_id?: string | null
    limit?: number | null
  }) {
    const response = await api.get<CustodyLogEntry[]>(
      '/api/governance/custody/logs',
      {
        params: {
          asset_id: params?.asset_id ?? undefined,
          asset_version_id: params?.asset_version_id ?? undefined,
          planner_session_id: params?.planner_session_id ?? undefined,
          compartment_id: params?.compartment_id ?? undefined,
          limit: params?.limit ?? undefined,
        },
      },
    )
    return response.data
  },
  async createCustodyLog(payload: CustodyLogCreate) {
    const response = await api.post<CustodyLogEntry>(
      '/api/governance/custody/logs',
      {
        ...payload,
        meta: payload.meta ?? {},
      },
    )
    return response.data
  },
}

const coerceNumber = (value: unknown): number | null => {
  if (value === null || value === undefined) {
    return null
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

export const mapGovernanceAnalyticsSummary = (
  summary: GovernanceAnalyticsPreviewSummary,
): GovernanceAnalyticsPreviewSummary => ({
  ...summary,
  blocked_ratio: Number(summary.blocked_ratio),
  ladder_load: Number(summary.ladder_load),
  override_actions_executed: Number(summary.override_actions_executed ?? 0),
  override_actions_reversed: Number(summary.override_actions_reversed ?? 0),
  override_cooldown_minutes: coerceNumber(summary.override_cooldown_minutes),
  sla_within_target_ratio: coerceNumber(summary.sla_within_target_ratio),
  mean_sla_delta_minutes: coerceNumber(summary.mean_sla_delta_minutes),
  approval_latency_minutes: coerceNumber(summary.approval_latency_minutes),
  publication_cadence_days: coerceNumber(summary.publication_cadence_days),
  blocker_churn_index: coerceNumber(summary.blocker_churn_index),
})

const mapLatencyBand = (
  band: GovernanceAnalyticsLatencyBand,
): GovernanceAnalyticsLatencyBand => ({
  ...band,
  start_minutes: coerceNumber(band.start_minutes),
  end_minutes: coerceNumber(band.end_minutes),
  count: Number(band.count ?? 0),
})

const mapLoadBandCounts = (
  counts: GovernanceReviewerLoadBandCounts,
): GovernanceReviewerLoadBandCounts => ({
  light: Number(counts.light ?? 0),
  steady: Number(counts.steady ?? 0),
  saturated: Number(counts.saturated ?? 0),
})

const mapScenarioOverrideAggregate = (
  bucket: GovernanceScenarioOverrideAggregate,
): GovernanceScenarioOverrideAggregate => ({
  scenario_id: bucket.scenario_id ?? null,
  scenario_name: bucket.scenario_name ?? null,
  folder_name: bucket.folder_name ?? null,
  executed_count: Number(bucket.executed_count ?? 0),
  reversed_count: Number(bucket.reversed_count ?? 0),
  net_count: Number(bucket.net_count ?? 0),
})

const mapNotebookOverrideAggregate = (
  bucket: GovernanceNotebookOverrideAggregate,
): GovernanceNotebookOverrideAggregate => ({
  notebook_entry_id: bucket.notebook_entry_id ?? null,
  notebook_title: bucket.notebook_title ?? null,
  execution_id: bucket.execution_id ?? null,
  executed_count: Number(bucket.executed_count ?? 0),
  reversed_count: Number(bucket.reversed_count ?? 0),
  net_count: Number(bucket.net_count ?? 0),
})

const mapGovernanceOverrideLineageAggregates = (
  summary: GovernanceOverrideLineageAggregates,
): GovernanceOverrideLineageAggregates => ({
  scenarios: summary.scenarios.map((item) => mapScenarioOverrideAggregate(item)),
  notebooks: summary.notebooks.map((item) => mapNotebookOverrideAggregate(item)),
})

export const mapGuardrailSimulationRecord = (
  record: GovernanceGuardrailSimulationRecord,
): GovernanceGuardrailSimulationRecord => ({
  ...record,
  metadata: record.metadata ?? {},
  projected_delay_minutes: Number(record.projected_delay_minutes ?? 0),
  summary: {
    ...record.summary,
    projected_delay_minutes: Number(record.summary.projected_delay_minutes ?? 0),
    reasons: Array.isArray(record.summary.reasons)
      ? [...record.summary.reasons]
      : [],
    regressed_stage_indexes: Array.isArray(record.summary.regressed_stage_indexes)
      ? [...record.summary.regressed_stage_indexes]
      : [],
  },
})

export const mapGovernanceReviewerCadence = (
  cadence: GovernanceReviewerCadenceSummary,
): GovernanceReviewerCadenceSummary => ({
  ...cadence,
  assignment_count: Number(cadence.assignment_count ?? 0),
  completion_count: Number(cadence.completion_count ?? 0),
  pending_count: Number(cadence.pending_count ?? 0),
  average_latency_minutes: coerceNumber(cadence.average_latency_minutes),
  latency_p50_minutes: coerceNumber(cadence.latency_p50_minutes),
  latency_p90_minutes: coerceNumber(cadence.latency_p90_minutes),
  blocked_ratio_trailing: coerceNumber(cadence.blocked_ratio_trailing),
  churn_signal: coerceNumber(cadence.churn_signal),
  latency_bands: cadence.latency_bands.map((band) => mapLatencyBand(band)),
})

export const mapGovernanceAnalyticsReport = (
  report: GovernanceAnalyticsReport,
): GovernanceAnalyticsReport => ({
  ...report,
  totals: {
    ...report.totals,
    average_blocked_ratio: Number(report.totals.average_blocked_ratio),
    total_new_blockers: Number(report.totals.total_new_blockers),
    total_resolved_blockers: Number(report.totals.total_resolved_blockers),
    average_sla_within_target_ratio: coerceNumber(
      report.totals.average_sla_within_target_ratio,
    ),
    total_baseline_versions: Number(report.totals.total_baseline_versions),
    total_rollbacks: Number(report.totals.total_rollbacks),
    average_approval_latency_minutes: coerceNumber(
      report.totals.average_approval_latency_minutes,
    ),
    average_publication_cadence_days: coerceNumber(
      report.totals.average_publication_cadence_days,
    ),
    reviewer_count: Number(report.totals.reviewer_count ?? 0),
    streak_alert_count: Number(report.totals.streak_alert_count ?? 0),
    reviewer_latency_p50_minutes: coerceNumber(
      report.totals.reviewer_latency_p50_minutes,
    ),
    reviewer_latency_p90_minutes: coerceNumber(
      report.totals.reviewer_latency_p90_minutes,
    ),
    reviewer_load_band_counts: mapLoadBandCounts(
      report.totals.reviewer_load_band_counts,
    ),
  },
  results: report.results.map((item) => mapGovernanceAnalyticsSummary(item)),
  reviewer_cadence: report.reviewer_cadence.map((item) =>
    mapGovernanceReviewerCadence(item),
  ),
  lineage_summary: mapGovernanceOverrideLineageAggregates(report.lineage_summary),
  meta: mapGovernanceAnalyticsMeta(report.meta),
})

const mapGovernanceAnalyticsMeta = (
  meta: Record<string, any> | GovernanceAnalyticsMeta | undefined,
): GovernanceAnalyticsMeta => {
  if (!meta) {
    return {}
  }

  const stageMetricsRaw = (meta as any).approval_stage_metrics ?? {}
  const stageMetrics: Record<string, GovernanceStageMetrics> = {}
  Object.entries(stageMetricsRaw).forEach(([exportId, metrics]) => {
    stageMetrics[exportId] = mapGovernanceStageMetrics(metrics)
  })

  const overdueSummaryRaw = (meta as any).overdue_stage_summary
  const overdueSummary = overdueSummaryRaw
    ? mapGovernanceOverdueStageSummary(overdueSummaryRaw)
    : undefined

  const payload: GovernanceAnalyticsMeta = {}
  if (Object.keys(stageMetrics).length > 0) {
    payload.approval_stage_metrics = stageMetrics
  }
  if (overdueSummary) {
    payload.overdue_stage_summary = overdueSummary
  }
  return payload
}

const mapGovernanceStageMetrics = (metrics: any): GovernanceStageMetrics => {
  const statusCountsEntries = Object.entries(metrics?.status_counts ?? {})
  const status_counts = statusCountsEntries.reduce<Record<string, number>>(
    (acc, [key, value]) => {
      acc[key] = Number(value ?? 0)
      return acc
    },
    {},
  )

  const detailsEntries = Object.entries(metrics?.stage_details ?? {})
  const stage_details = detailsEntries.reduce<
    Record<string, GovernanceStageDetailMetrics>
  >((acc, [stageId, detail]) => {
    acc[stageId] = mapGovernanceStageDetail(detail)
    return acc
  }, {})

  return {
    total: Number(metrics?.total ?? 0),
    overdue_count: Number(metrics?.overdue_count ?? 0),
    mean_resolution_minutes: coerceNumber(metrics?.mean_resolution_minutes),
    status_counts,
    stage_details,
  }
}

const mapGovernanceStageDetail = (detail: any): GovernanceStageDetailMetrics => ({
  status: typeof detail?.status === 'string' ? detail.status : 'unknown',
  breached: Boolean(detail?.breached),
  resolution_minutes: coerceNumber(detail?.resolution_minutes),
  due_at: detail?.due_at ?? null,
  completed_at: detail?.completed_at ?? null,
})

const mapGovernanceOverdueStageSummary = (
  summary: any,
): GovernanceOverdueStageSummary => ({
  total_overdue: Number(summary?.total_overdue ?? 0),
  open_overdue: Number(summary?.open_overdue ?? 0),
  resolved_overdue: Number(summary?.resolved_overdue ?? 0),
  overdue_exports: Array.isArray(summary?.overdue_exports)
    ? summary.overdue_exports.map((value: any) => String(value))
    : [],
  role_counts: Object.entries(summary?.role_counts ?? {}).reduce<
    Record<string, number>
  >((acc, [key, value]) => {
    acc[key] = Number(value ?? 0)
    return acc
  }, {}),
  mean_open_minutes: coerceNumber(summary?.mean_open_minutes),
  open_age_buckets: {
    lt60: Number(summary?.open_age_buckets?.lt60 ?? 0),
    '60to180': Number(summary?.open_age_buckets?.['60to180'] ?? 0),
    gt180: Number(summary?.open_age_buckets?.gt180 ?? 0),
  },
  trend: Array.isArray(summary?.trend)
    ? summary.trend.map((bucket: any) => mapGovernanceOverdueTrendBucket(bucket))
    : [],
  stage_samples: Array.isArray(summary?.stage_samples)
    ? summary.stage_samples.map((sample: any) =>
        mapGovernanceOverdueStageSample(sample),
      )
    : [],
})

const mapGovernanceOverdueTrendBucket = (
  bucket: any,
): GovernanceOverdueStageTrendBucket => ({
  date: String(bucket?.date ?? ''),
  count: Number(bucket?.count ?? 0),
})

const mapGovernanceOverdueStageSample = (
  sample: any,
): GovernanceOverdueStageSample => ({
  stage_id: String(sample?.stage_id ?? ''),
  export_id: String(sample?.export_id ?? ''),
  sequence_index: Number(sample?.sequence_index ?? 0),
  status: String(sample?.status ?? ''),
  role: sample?.role ?? null,
  due_at: sample?.due_at ?? null,
  detected_at: String(sample?.detected_at ?? ''),
})

const mapGovernanceReviewerCadenceTotals = (
  totals: GovernanceReviewerCadenceTotals,
): GovernanceReviewerCadenceTotals => ({
  reviewer_count: Number(totals.reviewer_count ?? 0),
  streak_alert_count: Number(totals.streak_alert_count ?? 0),
  reviewer_latency_p50_minutes: coerceNumber(
    totals.reviewer_latency_p50_minutes,
  ),
  reviewer_latency_p90_minutes: coerceNumber(
    totals.reviewer_latency_p90_minutes,
  ),
  load_band_counts: mapLoadBandCounts(totals.load_band_counts),
})

export const mapGovernanceReviewerCadenceReport = (
  report: GovernanceReviewerCadenceReport,
): GovernanceReviewerCadenceReport => ({
  reviewers: report.reviewers.map((item) => mapGovernanceReviewerCadence(item)),
  totals: mapGovernanceReviewerCadenceTotals(report.totals),
})

const mapGovernanceGuardrailStateBreakdown = (
  breakdown: any,
): Record<string, number> => {
  const result: Record<string, number> = {}
  if (breakdown && typeof breakdown === 'object') {
    Object.entries(breakdown).forEach(([key, value]) => {
      const numeric = Number(value ?? 0)
      result[String(key)] = Number.isFinite(numeric) ? numeric : 0
    })
  }
  return result
}

const mapGovernanceGuardrailHealthTotals = (
  totals: any,
): GovernanceGuardrailHealthTotals => ({
  total_exports: Number(totals?.total_exports ?? 0),
  blocked: Number(totals?.blocked ?? 0),
  awaiting_approval: Number(totals?.awaiting_approval ?? 0),
  queued: Number(totals?.queued ?? 0),
  ready: Number(totals?.ready ?? 0),
  failed: Number(totals?.failed ?? 0),
})

const mapGovernanceGuardrailQueueEntry = (
  entry: any,
): GovernanceGuardrailQueueEntry => ({
  export_id: String(entry?.export_id ?? ''),
  execution_id: String(entry?.execution_id ?? ''),
  version:
    entry?.version === undefined || entry?.version === null
      ? null
      : Number(entry.version),
  state: String(entry?.state ?? 'unknown'),
  event: entry?.event != null ? String(entry.event) : null,
  approval_status: String(entry?.approval_status ?? ''),
  artifact_status: String(entry?.artifact_status ?? ''),
  packaging_attempts: Number(entry?.packaging_attempts ?? 0),
  guardrail_state:
    entry?.guardrail_state === 'clear' || entry?.guardrail_state === 'blocked'
      ? entry.guardrail_state
      : null,
  projected_delay_minutes:
    entry?.projected_delay_minutes === undefined ||
    entry?.projected_delay_minutes === null
      ? null
      : Number(entry.projected_delay_minutes),
  pending_stage_id:
    entry?.pending_stage_id != null ? String(entry.pending_stage_id) : null,
  pending_stage_index:
    entry?.pending_stage_index === undefined || entry?.pending_stage_index === null
      ? null
      : Number(entry.pending_stage_index),
  pending_stage_status:
    entry?.pending_stage_status != null
      ? String(entry.pending_stage_status)
      : null,
  pending_stage_due_at:
    entry?.pending_stage_due_at != null
      ? String(entry.pending_stage_due_at)
      : null,
  updated_at: entry?.updated_at != null ? String(entry.updated_at) : null,
  context: entry?.context && typeof entry.context === 'object' ? entry.context : {},
})

export const mapGovernanceGuardrailHealthReport = (
  report: any,
): GovernanceGuardrailHealthReport => ({
  totals: mapGovernanceGuardrailHealthTotals(report?.totals ?? {}),
  state_breakdown: mapGovernanceGuardrailStateBreakdown(
    report?.state_breakdown ?? {},
  ),
  queue: Array.isArray(report?.queue)
    ? report.queue.map((item) => mapGovernanceGuardrailQueueEntry(item))
    : [],
})
