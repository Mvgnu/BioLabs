import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import GovernanceWorkspacePage from '../../../governance/page'
import type { GovernanceTemplate, GovernanceTemplateAssignment } from '../../../types'

vi.mock('../../governance/LadderBuilder', () => ({
  default: ({ stages, onChange }: { stages: any[]; onChange: (next: any[]) => void }) => (
    <div>
      <p data-testid="ladder-stage-count">{stages.length}</p>
      <button type="button" onClick={() => onChange([...stages, { required_role: 'scientist' }])}>
        Add stage
      </button>
    </div>
  ),
}))

vi.mock('../../governance/LadderSimulationWidget', () => ({
  default: () => <div data-testid="ladder-simulation" />,
}))

const mutateAsync = vi.fn()
const createAssignmentMutate = vi.fn()
const deleteAssignmentMutate = vi.fn()
const previewMutate = vi.fn()

const baseTemplate: GovernanceTemplate = {
  id: 'template-1',
  template_key: 'governance.baseline',
  name: 'Baseline',
  description: 'Baseline ladder',
  version: 1,
  status: 'published',
  default_stage_sla_hours: 24,
  permitted_roles: ['scientist', 'quality'],
  stage_blueprint: [
    { required_role: 'scientist', name: 'Scientist review', sla_hours: 24, metadata: {} },
  ],
  forked_from_id: null,
  is_latest: true,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  published_at: new Date().toISOString(),
  created_by_id: 'user-1',
}

const newTemplateResponse = (overrides: Partial<GovernanceTemplate> = {}): GovernanceTemplate => ({
  ...baseTemplate,
  id: overrides.id ?? 'template-new',
  version: overrides.version ?? 2,
  status: overrides.status ?? 'draft',
  forked_from_id: overrides.forked_from_id ?? baseTemplate.id,
  ...overrides,
})

vi.mock('../../../hooks/useGovernance', () => ({
  useGovernanceTemplates: () => ({ data: [baseTemplate], isLoading: false }),
  useGovernanceTemplate: () => ({ data: undefined }),
  useCreateGovernanceTemplate: () => ({ mutateAsync, isPending: false }),
  useGovernanceAssignments: () => ({ data: [] as GovernanceTemplateAssignment[] }),
  useCreateGovernanceAssignment: () => ({ mutate: createAssignmentMutate }),
  useDeleteGovernanceAssignment: () => ({ mutate: deleteAssignmentMutate }),
}))

vi.mock('../../../hooks/useExperimentConsole', () => ({
  useExperimentPreview: () => ({ mutateAsync: previewMutate, isPending: false, reset: vi.fn() }),
  useCreateScenarioFolder: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

vi.mock('../../../components/ui', async () => {
  const ui = await vi.importActual<typeof import('../../../components/ui')>(
    '../../../components/ui'
  )
  return {
    ...ui,
  }
})

describe('GovernanceWorkspacePage', () => {
  beforeEach(() => {
    mutateAsync.mockReset()
    createAssignmentMutate.mockReset()
    deleteAssignmentMutate.mockReset()
    previewMutate.mockReset()
  })

  it('persists a draft for a new template', async () => {
    mutateAsync.mockResolvedValueOnce(newTemplateResponse({ status: 'draft' }))

    render(<GovernanceWorkspacePage />)

    const keyInput = screen.getByLabelText(/template key/i)
    fireEvent.change(keyInput, { target: { value: 'governance.new' } })

    const nameInput = screen.getByLabelText(/template name/i)
    fireEvent.change(nameInput, { target: { value: 'New Template' } })

    fireEvent.click(screen.getByRole('button', { name: /save draft/i }))

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledTimes(1)
      expect(mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          template_key: 'governance.new',
          name: 'New Template',
          publish: false,
        })
      )
    })
  })

  it('forks an existing template and publishes a new version', async () => {
    mutateAsync.mockResolvedValueOnce(newTemplateResponse({ id: 'template-2', status: 'published' }))

    render(<GovernanceWorkspacePage />)

    const openButtons = screen.getAllByRole('button', { name: /open/i })
    fireEvent.click(openButtons[0])

    const forkButtons = screen.getAllByRole('button', { name: /fork/i })
    fireEvent.click(forkButtons[0])

    const nameInputs = screen.getAllByLabelText(/template name/i)
    fireEvent.change(nameInputs[nameInputs.length - 1], { target: { value: 'Baseline v2' } })

    const publishButtons = screen.getAllByRole('button', { name: /publish/i })
    fireEvent.click(publishButtons[publishButtons.length - 1])

    await waitFor(() => {
      expect(mutateAsync).toHaveBeenCalledTimes(1)
      expect(mutateAsync).toHaveBeenCalledWith(
        expect.objectContaining({
          publish: true,
          name: 'Baseline v2',
        })
      )
    })
  })
})
