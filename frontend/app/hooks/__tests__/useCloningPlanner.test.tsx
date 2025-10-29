import React from 'react'
import { act, renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { CloningPlannerSession } from '../../types'
import api from '../../api/client'
import {
  cancelCloningPlannerSession,
  finalizeCloningPlannerSession,
  getCloningPlannerSession,
  resumeCloningPlannerSession,
  submitCloningPlannerStage,
} from '../../api/cloningPlanner'
import { useCloningPlanner } from '../useCloningPlanner'

vi.mock('../../api/cloningPlanner', () => ({
  getCloningPlannerSession: vi.fn(),
  submitCloningPlannerStage: vi.fn(),
  resumeCloningPlannerSession: vi.fn(),
  finalizeCloningPlannerSession: vi.fn(),
  cancelCloningPlannerSession: vi.fn(),
}))

class MockEventSource {
  url: string
  onmessage: ((event: MessageEvent<any>) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  readyState = 1

  constructor(url: string) {
    this.url = url
  }

  emit(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent)
  }

  close() {
    this.readyState = 2
  }

  addEventListener(): void {}
  removeEventListener(): void {}
  dispatchEvent(): boolean {
    return false
  }
}

const createClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })

const wrapper = (client: QueryClient) =>
  ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )

const sessionFixture = (): CloningPlannerSession => ({
  id: 'planner-1',
  created_by_id: 'user-1',
  status: 'primers_running',
  assembly_strategy: 'gibson',
  input_sequences: [{ name: 'vector', sequence: 'ATGC', metadata: { length: 4 } }],
  primer_set: { primers: [] },
  restriction_digest: { digests: [] },
  assembly_plan: { steps: [] },
  qc_reports: { reports: [] },
  inventory_reservations: [],
  guardrail_state: { primers: { primer_state: 'review' } },
  guardrail_gate: { active: false, reasons: [] },
  branch_state: { branches: { 'branch-main': { id: 'branch-main', label: 'main' } }, order: ['branch-main'] },
  active_branch_id: 'branch-main',
  timeline_cursor: 'cursor-initial',
  stage_timings: {
    intake: { status: 'intake_recorded', completed_at: '2024-01-01T00:00:00.000Z' },
    primers: { status: 'primers_running', retries: 0 },
  },
  current_step: 'primers',
  celery_task_id: null,
  last_error: null,
  created_at: '2024-01-01T00:00:00.000Z',
  updated_at: '2024-01-01T00:00:00.000Z',
  completed_at: null,
  stage_history: [],
  qc_artifacts: [],
})

beforeEach(() => {
  vi.clearAllMocks()
  ;(api.defaults as any).baseURL = ''
})

describe('useCloningPlanner', () => {
  it('fetches planner session data and exposes helper mutations', async () => {
    const client = createClient()
    const eventSource = new MockEventSource('/api/cloning-planner/sessions/planner-1/events')
    const eventFactory = vi.fn(() => eventSource as unknown as EventSource)
    ;(getCloningPlannerSession as ReturnType<typeof vi.fn>).mockResolvedValue(sessionFixture())
    ;(submitCloningPlannerStage as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...sessionFixture(),
      status: 'restriction_running',
      current_step: 'restriction',
    })

    const { result } = renderHook(() => useCloningPlanner('planner-1', { eventSourceFactory: eventFactory }), {
      wrapper: wrapper(client),
    })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.data?.id).toBe('planner-1')
    expect(result.current.recoveryBundle).toBeNull()

    await act(async () => {
      await result.current.runStage('primers', { payload: { target_tm: 60 } })
    })

    expect(submitCloningPlannerStage).toHaveBeenCalledWith('planner-1', 'primers', {
      payload: { target_tm: 60 },
    })
    await waitFor(() => expect(result.current.data?.current_step).toBe('restriction'))
  })

  it('subscribes to event stream and records events', async () => {
    const client = createClient()
    const eventSource = new MockEventSource('/api/cloning-planner/sessions/planner-1/events')
    const eventFactory = vi.fn(() => eventSource as unknown as EventSource)
    const invalidateSpy = vi.spyOn(client, 'invalidateQueries')
    ;(getCloningPlannerSession as ReturnType<typeof vi.fn>).mockResolvedValue(sessionFixture())

    const { result } = renderHook(() => useCloningPlanner('planner-1', { eventSourceFactory: eventFactory }), {
      wrapper: wrapper(client),
    })

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    act(() => {
      eventSource.emit({
        type: 'stage_completed',
        session_id: 'planner-1',
        status: 'ready_for_finalize',
        current_step: 'restriction',
        payload: { stage: 'primers' },
        timestamp: new Date().toISOString(),
        recovery_bundle: {
          stage: 'primers',
          resume_token: {
            session_id: 'planner-1',
            checkpoint: 'primers',
          },
          guardrail_reasons: ['custody_status:halted'],
          resume_ready: true,
        },
        drill_summaries: [
          {
            event_id: 'evt-1',
            status: 'open',
            resume_ready: false,
          },
        ],
      })
    })

    await waitFor(() => expect(result.current.events.length).toBe(1))
    expect(invalidateSpy).toHaveBeenCalled()
    expect(result.current.recoveryBundle?.stage).toBe('primers')
    expect(result.current.recoveryBundle?.drill_summaries?.length).toBe(1)
    expect(result.current.latestResumeToken?.checkpoint).toBe('primers')
  })

  it('exposes resume and finalize helpers', async () => {
    const client = createClient()
    const eventFactory = vi.fn(() => new MockEventSource('/api/cloning-planner/sessions/planner-1/events') as unknown as EventSource)
    ;(getCloningPlannerSession as ReturnType<typeof vi.fn>).mockResolvedValue(sessionFixture())
    ;(resumeCloningPlannerSession as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...sessionFixture(),
      status: 'ready_for_finalize',
    })
    ;(finalizeCloningPlannerSession as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...sessionFixture(),
      status: 'finalized',
      completed_at: '2024-01-02T00:00:00.000Z',
    })
    ;(cancelCloningPlannerSession as ReturnType<typeof vi.fn>).mockResolvedValue({
      ...sessionFixture(),
      status: 'cancelled',
    })

    const { result } = renderHook(() => useCloningPlanner('planner-1', { eventSourceFactory: eventFactory }), {
      wrapper: wrapper(client),
    })

    await waitFor(() => expect(result.current.isLoading).toBe(false))

    await act(async () => {
      await result.current.resume({ overrides: { enzymes: ['EcoRI'] } })
      await result.current.finalize({ guardrail_state: { qc: { breaches: [] } } })
      await result.current.cancel({ reason: 'operator abort' })
    })

    expect(resumeCloningPlannerSession).toHaveBeenCalledWith('planner-1', { overrides: { enzymes: ['EcoRI'] } })
    expect(finalizeCloningPlannerSession).toHaveBeenCalledWith('planner-1', {
      guardrail_state: { qc: { breaches: [] } },
    })
    expect(cancelCloningPlannerSession).toHaveBeenCalledWith('planner-1', { reason: 'operator abort' })
  })
})

