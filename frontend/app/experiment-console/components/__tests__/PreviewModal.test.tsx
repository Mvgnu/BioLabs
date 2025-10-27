import { fireEvent, render, screen } from '@testing-library/react'
import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PreviewModal from '../PreviewModal'
import type { ExperimentScenarioWorkspace } from '../../../types'

const mocks = vi.hoisted(() => ({
  useScenarioWorkspace: vi.fn(),
  useExperimentPreview: vi.fn(),
  useCreateScenario: vi.fn(),
  useCreateScenarioFolder: vi.fn(),
  useUpdateScenario: vi.fn(),
  useCloneScenario: vi.fn(),
  useDeleteScenario: vi.fn(),
}))

vi.mock('../../../hooks/useExperimentConsole', () => mocks)

const {
  useScenarioWorkspace: mockUseScenarioWorkspace,
  useExperimentPreview: mockUseExperimentPreview,
  useCreateScenario: mockUseCreateScenario,
  useCreateScenarioFolder: mockUseCreateScenarioFolder,
  useUpdateScenario: mockUseUpdateScenario,
  useCloneScenario: mockUseCloneScenario,
  useDeleteScenario: mockUseDeleteScenario,
} = mocks

describe('PreviewModal', () => {
  const workspaceData: ExperimentScenarioWorkspace = {
    execution: {
      id: 'exec-1',
      template_id: 'template-1',
      template_name: 'Protocol A',
      template_version: '1',
      run_by_id: 'user-1',
      status: 'in_progress',
    },
    snapshots: [
      {
        id: 'snap-1',
        template_id: 'gov-1',
        template_key: 'governance.baseline',
        template_name: 'Baseline Ladder',
        version: 1,
        status: 'published',
        captured_at: new Date('2024-01-01T08:00:00Z').toISOString(),
        captured_by_id: 'user-1',
      },
    ],
    scenarios: [
      {
        id: 'scenario-1',
        execution_id: 'exec-1',
        owner_id: 'user-1',
        team_id: null,
        workflow_template_snapshot_id: 'snap-1',
        name: 'Throughput uplift',
        description: 'Extend SLA window for first stage',
        resource_overrides: {
          inventory_item_ids: ['inv-1'],
          booking_ids: [],
          equipment_ids: [],
        },
        stage_overrides: [
          {
            index: 0,
            sla_hours: 80,
            assignee_id: 'scientist-2',
            delegate_id: null,
          },
        ],
        cloned_from_id: null,
        folder_id: null,
        is_shared: false,
        shared_team_ids: [],
        expires_at: null,
        timeline_event_id: null,
        created_at: new Date('2024-01-01T12:00:00Z').toISOString(),
        updated_at: new Date('2024-01-02T12:00:00Z').toISOString(),
      },
    ],
    folders: [
      {
        id: 'folder-1',
        execution_id: 'exec-1',
        name: 'Team Reviews',
        description: 'Shared scenarios',
        owner_id: 'user-1',
        team_id: null,
        visibility: 'private',
        created_at: new Date('2024-01-01T10:00:00Z').toISOString(),
        updated_at: new Date('2024-01-01T10:00:00Z').toISOString(),
      },
    ],
  }

  const previewResponse = {
    execution_id: 'exec-1',
    snapshot_id: 'snap-1',
    baseline_snapshot_id: 'snap-1',
    generated_at: new Date().toISOString(),
    template_name: 'Protocol A',
    template_version: 1,
    stage_insights: [
      {
        index: 0,
        name: 'Scientist review',
        required_role: 'scientist',
        status: 'ready',
        sla_hours: 80,
        projected_due_at: new Date().toISOString(),
        blockers: [],
        required_actions: [],
        auto_triggers: [],
        assignee_id: 'scientist-2',
        delegate_id: null,
        mapped_step_indexes: [0],
        gate_keys: [],
        baseline_status: 'ready',
        baseline_sla_hours: 48,
        baseline_projected_due_at: new Date().toISOString(),
        baseline_assignee_id: 'scientist-1',
        baseline_delegate_id: null,
        baseline_blockers: [],
        delta_status: 'unchanged',
        delta_sla_hours: 32,
        delta_projected_due_minutes: 0,
        delta_new_blockers: [],
        delta_resolved_blockers: [],
      },
    ],
    narrative_preview: '# Scenario preview',
    resource_warnings: [],
  }

  const previewMutate = vi.fn().mockResolvedValue(previewResponse)

  beforeEach(() => {
    mockUseScenarioWorkspace.mockReturnValue({
      data: workspaceData,
      isLoading: false,
      isError: false,
    })
    mockUseExperimentPreview.mockReturnValue({
      mutateAsync: previewMutate,
      isPending: false,
      reset: vi.fn(),
    })
    mockUseCreateScenario.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseCreateScenarioFolder.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseUpdateScenario.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseCloneScenario.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    mockUseDeleteScenario.mockReturnValue({ mutateAsync: vi.fn(), isPending: false })
    previewMutate.mockClear()
  })

  it('renders scenario list and runs preview for the selected scenario', async () => {
    render(<PreviewModal executionId="exec-1" open onClose={() => {}} />)

    expect(screen.getByRole('button', { name: 'Throughput uplift' })).toBeTruthy()

    const runButtons = screen.getAllByRole('button', { name: /^Run$/i })
    fireEvent.click(runButtons[0])

    expect(previewMutate).toHaveBeenCalledWith({
      workflow_template_snapshot_id: 'snap-1',
      stage_overrides: workspaceData.scenarios[0].stage_overrides,
      resource_overrides: workspaceData.scenarios[0].resource_overrides,
    })
  })

  it('allows drafting a new scenario', () => {
    render(<PreviewModal executionId="exec-1" open onClose={() => {}} />)

    const [initialScenarioName] = screen.getAllByLabelText(/scenario name/i)
    expect((initialScenarioName as HTMLInputElement).value).toBe('Throughput uplift')

    const [newButton] = screen.getAllByRole('button', { name: /new scenario/i })
    fireEvent.click(newButton)

    const [updatedScenarioName] = screen.getAllByLabelText(/scenario name/i)
    expect((updatedScenarioName as HTMLInputElement).value).toBe('')
  })
})
