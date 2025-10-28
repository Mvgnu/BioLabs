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

const mapGuardrailSimulationRecord = (
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
