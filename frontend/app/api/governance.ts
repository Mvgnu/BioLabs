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
  GovernanceAnalyticsReviewerLoad,
  GovernanceAnalyticsLatencyBand,
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
      { params },
    )
    return mapGovernanceAnalyticsReport(response.data)
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

export const mapGovernanceReviewerLoad = (
  load: GovernanceAnalyticsReviewerLoad,
): GovernanceAnalyticsReviewerLoad => ({
  ...load,
  average_latency_minutes: coerceNumber(load.average_latency_minutes),
  recent_blocked_ratio: coerceNumber(load.recent_blocked_ratio),
  baseline_churn: coerceNumber(load.baseline_churn),
  latency_bands: load.latency_bands.map((band) => mapLatencyBand(band)),
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
  },
  results: report.results.map((item) => mapGovernanceAnalyticsSummary(item)),
  reviewer_loads: report.reviewer_loads.map((item) => mapGovernanceReviewerLoad(item)),
})
