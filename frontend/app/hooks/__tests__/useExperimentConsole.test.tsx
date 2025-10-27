import type { ReactNode } from 'react'
import React from 'react'
import { act, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type {
  ExecutionNarrativeApprovalStage,
  ExecutionNarrativeApprovalAction,
  ExecutionNarrativeDelegationRequest,
  ExecutionNarrativeExportHistory,
  ExecutionNarrativeExportRecord,
  ExecutionNarrativeStageResetRequest,
} from '../../types'
import {
  useApproveNarrativeExport,
  useDelegateNarrativeApprovalStage,
  useResetNarrativeApprovalStage,
} from '../useExperimentConsole'
import api from '../../api/client'

vi.mock('../../api/client', () => {
  return {
    default: {
      get: vi.fn(),
      post: vi.fn(),
    },
  }
})

// purpose: validate react-query cache updates for staged narrative approvals
// status: pilot
// related_docs: docs/approval_workflow_design.md

const executionId = 'exec-1'

const baseUser = {
  id: 'user-1',
  email: 'scientist@example.com',
  full_name: 'Scientist One',
}

const otherUser = {
  id: 'user-2',
  email: 'reviewer@example.com',
  full_name: 'Reviewer Two',
}

const stage = (overrides?: Partial<ExecutionNarrativeApprovalStage>): ExecutionNarrativeApprovalStage => {
  const defaultActions: ExecutionNarrativeApprovalAction[] = []
  return {
    id: 'stage-1',
    export_id: 'export-1',
    sequence_index: 0,
    required_role: 'scientist',
    status: 'pending',
    metadata: {},
    actions: defaultActions,
    ...overrides,
  }
}

const record = (
  overrides?: Partial<ExecutionNarrativeExportRecord>,
): ExecutionNarrativeExportRecord => ({
  id: 'export-1',
  execution_id: executionId,
  version: 1,
  format: 'markdown',
  generated_at: '2024-01-01T00:00:00.000Z',
  event_count: 5,
  content: '# Narrative',
  approval_status: 'pending',
  approval_stage_count: 1,
  requested_by: baseUser,
  approval_stages: [stage()],
  attachments: [],
  metadata: {},
  artifact_status: 'queued',
  created_at: '2024-01-01T00:00:00.000Z',
  updated_at: '2024-01-01T00:00:00.000Z',
  ...overrides,
})

const withQueryClient = (client: QueryClient) => {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
}

describe('useExperimentConsole approval mutations', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('promotes approved exports to the top of cached history and invalidates timeline queries', async () => {
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
    const existing: ExecutionNarrativeExportHistory = {
      exports: [record({ id: 'export-2', approval_status: 'pending' }), record()],
    }
    qc.setQueryData(['experiment-console', 'exports', executionId], existing)

    const approved = record({
      approval_status: 'approved',
      approved_by: otherUser,
      approval_stages: [stage({ status: 'approved', completed_at: '2024-01-02T00:00:00.000Z' })],
      id: 'export-1',
    })

    ;(api.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: approved })

    const { result } = renderHook(() => useApproveNarrativeExport(executionId), {
      wrapper: withQueryClient(qc),
    })

    await act(async () => {
      await result.current.mutateAsync({
        exportId: 'export-1',
        approval: { status: 'approved', signature: 'sig-1' },
      })
    })

    expect(api.post).toHaveBeenCalledWith(
      `/api/experiment-console/sessions/${executionId}/exports/narrative/export-1/approve`,
      { status: 'approved', signature: 'sig-1' },
    )

    const updated = qc.getQueryData<ExecutionNarrativeExportHistory>([
      'experiment-console',
      'exports',
      executionId,
    ])
    expect(updated?.exports[0]).toEqual(approved)
    expect(updated?.exports).toHaveLength(2)

    expect(invalidateSpy).toHaveBeenCalledTimes(1)
    const args = invalidateSpy.mock.calls[0]?.[0] as { predicate?: (query: { queryKey: any }) => boolean }
    expect(args?.predicate?.({
      queryKey: ['experiment-console', 'timeline', executionId, undefined],
    } as any)).toBe(true)
  })

  it('replaces delegated stages within cached history without duplicating exports', async () => {
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
    const current = record({ id: 'export-3' })
    const history: ExecutionNarrativeExportHistory = {
      exports: [current, record()],
    }
    qc.setQueryData(['experiment-console', 'exports', executionId], history)

    const delegated = record({
      id: 'export-3',
      approval_status: 'pending',
      approval_stages: [
        stage({
          id: 'stage-3',
          status: 'delegated',
          delegated_to: otherUser,
          actions: [
            {
              id: 'action-1',
              stage_id: 'stage-3',
              action_type: 'delegated',
              actor: baseUser,
              delegation_target: otherUser,
              metadata: {},
              created_at: '2024-01-01T02:00:00.000Z',
              notes: 'Need secondary review',
            },
          ],
          metadata: {},
        }),
      ],
    })

    ;(api.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: delegated })

    const { result } = renderHook(() => useDelegateNarrativeApprovalStage(executionId), {
      wrapper: withQueryClient(qc),
    })

    const delegation: ExecutionNarrativeDelegationRequest = {
      delegate_id: otherUser.id,
      notes: 'Need secondary review',
    }

    await act(async () => {
      await result.current.mutateAsync({
        exportId: 'export-3',
        stageId: 'stage-3',
        delegation,
      })
    })

    expect(api.post).toHaveBeenCalledWith(
      `/api/experiment-console/sessions/${executionId}/exports/narrative/export-3/stages/stage-3/delegate`,
      delegation,
    )

    const updated = qc.getQueryData<ExecutionNarrativeExportHistory>([
      'experiment-console',
      'exports',
      executionId,
    ])
    expect(updated?.exports[0]).toEqual(delegated)
    expect(updated?.exports).toHaveLength(2)
    expect(updated?.exports.filter((exp) => exp.id === 'export-3')).toHaveLength(1)
    expect(invalidateSpy).toHaveBeenCalled()
  })

  it('hydrates history when resets occur before any cached exports exist', async () => {
    const qc = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    })
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')

    const resetRecord = record({
      id: 'export-4',
      approval_status: 'pending',
      approval_stages: [
        stage({
          id: 'stage-4',
          status: 'reset',
          notes: 'Need revised evidence',
          actions: [
            {
              id: 'action-2',
              stage_id: 'stage-4',
              action_type: 'reset',
              actor: otherUser,
              metadata: {},
              created_at: '2024-01-03T00:00:00.000Z',
              notes: 'Need revised evidence',
            },
          ],
          metadata: {},
        }),
      ],
    })

    ;(api.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: resetRecord })

    const { result } = renderHook(() => useResetNarrativeApprovalStage(executionId), {
      wrapper: withQueryClient(qc),
    })

    const reset: ExecutionNarrativeStageResetRequest = {
      notes: 'Need revised evidence',
    }

    await act(async () => {
      await result.current.mutateAsync({
        exportId: 'export-4',
        stageId: 'stage-4',
        reset,
      })
    })

    expect(api.post).toHaveBeenCalledWith(
      `/api/experiment-console/sessions/${executionId}/exports/narrative/export-4/stages/stage-4/reset`,
      reset,
    )

    const updated = qc.getQueryData<ExecutionNarrativeExportHistory>([
      'experiment-console',
      'exports',
      executionId,
    ])
    expect(updated?.exports).toHaveLength(1)
    expect(updated?.exports[0]).toEqual(resetRecord)
    expect(invalidateSpy).toHaveBeenCalled()
  })
})
