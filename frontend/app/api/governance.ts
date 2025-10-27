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
