import { fireEvent, render, screen } from '@testing-library/react'
import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import SharingWorkspacePage from '../page'
import type { DNARepository } from '../../types'

const mocks = vi.hoisted(() => ({
  useRepositories: vi.fn(),
  useCreateRelease: vi.fn(),
  useApproveRelease: vi.fn(),
  useAddCollaborator: vi.fn(),
  useRepositoryTimeline: vi.fn(),
    useSharingReviewStream: vi.fn(),
  }))

vi.mock('../../hooks/useSharingWorkspace', () => mocks)

  const {
    useRepositories: mockUseRepositories,
    useCreateRelease: mockUseCreateRelease,
    useApproveRelease: mockUseApproveRelease,
    useAddCollaborator: mockUseAddCollaborator,
    useRepositoryTimeline: mockUseRepositoryTimeline,
    useSharingReviewStream: mockUseSharingReviewStream,
  } = mocks

describe('SharingWorkspacePage', () => {
  const approveMutate = vi.fn()
  const releaseMutate = vi.fn()
  const collaboratorMutate = vi.fn()

  const repository: DNARepository = {
    id: 'repo-1',
    name: 'Genome Vault',
    slug: 'genome-vault',
    description: 'Governed repository',
    owner_id: 'user-owner',
    team_id: null,
    guardrail_policy: {
      name: 'Strict Policy',
      approval_threshold: 1,
      requires_custody_clearance: true,
      requires_planner_link: true,
      mitigation_playbooks: ['playbooks/custody-clearance'],
    },
    created_at: new Date('2024-01-01T00:00:00Z').toISOString(),
    updated_at: new Date('2024-01-02T00:00:00Z').toISOString(),
    collaborators: [
      {
        id: 'collab-1',
        repository_id: 'repo-1',
        user_id: 'user-maintainer',
        role: 'maintainer',
        invitation_status: 'active',
        created_at: new Date('2024-01-02T00:00:00Z').toISOString(),
      },
    ],
      releases: [
        {
          id: 'rel-1',
          repository_id: 'repo-1',
          version: 'v1.0.0',
          title: 'Initial release',
          notes: 'Ready to ship',
          status: 'awaiting_approval',
          guardrail_state: 'cleared',
          guardrail_snapshot: { custody_status: 'clear', breaches: [] },
          mitigation_summary: null,
          created_by_id: 'user-maintainer',
          planner_session_id: null,
          lifecycle_snapshot: { source: 'planner' },
          mitigation_history: [],
          replay_checkpoint: { checkpoint: 'final' },
          created_at: new Date('2024-01-02T00:00:00Z').toISOString(),
          updated_at: new Date('2024-01-02T00:00:00Z').toISOString(),
          published_at: null,
          approvals: [],
        },
      ],
      federation_links: [],
      release_channels: [],
    }

  beforeEach(() => {
    approveMutate.mockReset()
    releaseMutate.mockReset()
    collaboratorMutate.mockReset()

    mockUseRepositories.mockReturnValue({ data: [repository] })
    mockUseCreateRelease.mockReturnValue({ mutate: releaseMutate, isPending: false })
      mockUseApproveRelease.mockReturnValue({ mutate: approveMutate, isPending: false })
      mockUseAddCollaborator.mockReturnValue({ mutate: collaboratorMutate, isPending: false })
      mockUseRepositoryTimeline.mockReturnValue({
        data: [
          {
          id: 'timeline-1',
          repository_id: 'repo-1',
          release_id: 'rel-1',
          event_type: 'release.created',
          payload: { version: 'v1.0.0' },
          created_at: new Date('2024-01-02T00:00:00Z').toISOString(),
          created_by_id: 'user-maintainer',
        },
        ],
      })
      mockUseSharingReviewStream.mockReturnValue({ isConnected: false, close: vi.fn() })
    })

  it('renders repository details and guardrail policy', () => {
    render(<SharingWorkspacePage />)

    expect(screen.getByText('DNA Sharing Repositories')).toBeDefined()
    expect(screen.getAllByText('Genome Vault')[0]).toBeDefined()
    expect(screen.getByText('Strict Policy')).toBeDefined()
    expect(screen.getByText('Approvals Required')).toBeDefined()
    expect(screen.getByText('Guardrail Policy')).toBeDefined()
  })

  it('approves a release via mutation', () => {
    render(<SharingWorkspacePage />)

    const approveButtons = screen.getAllByRole('button', { name: /approve/i })
    fireEvent.click(approveButtons[0])

    expect(approveMutate).toHaveBeenCalledWith({
      id: 'rel-1',
      data: { status: 'approved', guardrail_flags: [], notes: 'Approved from workspace' },
    })
  })
})
