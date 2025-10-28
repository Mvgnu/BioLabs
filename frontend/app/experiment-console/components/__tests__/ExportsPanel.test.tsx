import React from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import ExportsPanel from '../ExportsPanel'
import type {
  ExecutionEvent,
  ExecutionNarrativeApprovalStage,
  ExecutionNarrativeExportRecord,
  GovernanceGuardrailSimulationRecord,
} from '../../../types'

const baseUser = {
  id: 'user-1',
  email: 'reviewer@example.com',
  full_name: 'Reviewer Example',
}

const guardrailSimulation: GovernanceGuardrailSimulationRecord = {
  id: 'simulation-1',
  execution_id: 'exec-1',
  actor: baseUser,
  created_at: '2024-01-01T00:10:00.000Z',
  state: 'blocked',
  projected_delay_minutes: 180,
  metadata: {},
  summary: {
    state: 'blocked',
    reasons: ['qa awaiting-evidence'],
    regressed_stage_indexes: [0],
    projected_delay_minutes: 180,
  },
}

const approvalStage = (overrides?: Partial<ExecutionNarrativeApprovalStage>): ExecutionNarrativeApprovalStage => ({
  id: 'stage-1',
  export_id: 'export-1',
  sequence_index: 1,
  name: 'Scientist Review',
  required_role: 'scientist',
  status: 'in_progress',
  sla_hours: 2,
  started_at: '2024-01-01T00:00:00.000Z',
  due_at: null,
  completed_at: null,
  assignee: baseUser,
  delegated_to: null,
  overdue_notified_at: null,
  notes: null,
  metadata: {},
  actions: [],
  ...overrides,
})

const exportRecord: ExecutionNarrativeExportRecord = {
  id: 'export-1',
  execution_id: 'exec-1',
  version: 1,
  format: 'markdown',
  generated_at: '2024-01-01T00:00:00.000Z',
  event_count: 3,
  content: '# Narrative',
  approval_status: 'pending',
  approval_stage_count: 1,
  workflow_template_id: null,
  workflow_template_snapshot_id: null,
  workflow_template_key: null,
  workflow_template_version: null,
  workflow_template_snapshot: {},
  current_stage: approvalStage(),
  current_stage_started_at: '2024-01-01T00:00:00.000Z',
  requested_by: baseUser,
  approved_by: null,
  notes: null,
  approval_stages: [approvalStage()],
  attachments: [],
  metadata: {},
  guardrail_simulation: guardrailSimulation,
  artifact_status: 'queued',
  artifact_checksum: null,
  artifact_error: null,
  artifact_file: null,
  artifact_download_path: null,
  artifact_signed_url: null,
  artifact_manifest_digest: null,
  packaging_attempts: 0,
  packaged_at: null,
  retired_at: null,
  retention_expires_at: null,
  created_at: '2024-01-01T00:00:00.000Z',
  updated_at: '2024-01-01T00:00:00.000Z',
}

const renderWithQueryClient = (ui: React.ReactNode) => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}

vi.mock('../../../hooks/useExperimentConsole', async () => {
  const actual = await vi.importActual<typeof import('../../../hooks/useExperimentConsole')>(
    '../../../hooks/useExperimentConsole',
  )
  return {
    ...actual,
    useExecutionNarrativeExports: () => ({
      data: { exports: [exportRecord] },
      isLoading: false,
      isError: false,
    }),
    useCreateNarrativeExport: () => ({ mutateAsync: vi.fn(), isLoading: false }),
    useApproveNarrativeExport: () => ({ mutateAsync: vi.fn(), isLoading: false }),
    useDelegateNarrativeApprovalStage: () => ({ mutateAsync: vi.fn(), isLoading: false }),
    useResetNarrativeApprovalStage: () => ({ mutateAsync: vi.fn(), isLoading: false }),
  }
})

describe('ExportsPanel guardrail integration', () => {
  const timelineEvents: ExecutionEvent[] = []

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders guardrail warnings and disables approvals when forecast is blocked', () => {
    renderWithQueryClient(<ExportsPanel executionId="exec-1" timelineEvents={timelineEvents} />)

    expect(screen.getByText('Guardrail blocked')).toBeDefined()
    expect(screen.getByText(/Forecast blocked/)).toBeDefined()
    expect(screen.getByText(/qa awaiting-evidence/)).toBeDefined()

    const approveButton = screen.getByRole('button', { name: /Approve stage/i })
    expect((approveButton as HTMLButtonElement).disabled).toBe(true)
  })
})
