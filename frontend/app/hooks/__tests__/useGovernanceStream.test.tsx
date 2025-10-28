import React from 'react'
import { act, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'

import type { GovernanceDecisionTimelinePage } from '../../types'
import { useGovernanceStream } from '../useGovernanceStream'

class MockEventSource {
  onmessage: ((event: MessageEvent<any>) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  readyState = 1
  url: string

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

const createWrapper = (client: QueryClient) => {
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
}

describe('useGovernanceStream', () => {
  it('merges snapshot payloads into governance timeline cache', () => {
    const client = new QueryClient()
    const wrapper = createWrapper(client)
    const mockSource = new MockEventSource('/api/experiment-console/governance/timeline/stream')
    const eventSourceFactory = vi.fn(() => mockSource as unknown as EventSource)

    const page: GovernanceDecisionTimelinePage = {
      entries: [
        {
          entry_id: 'event-1',
          entry_type: 'override_action',
          occurred_at: new Date().toISOString(),
          execution_id: 'exec-1',
          baseline_id: null,
          rule_key: 'cadence_overload',
          action: 'reassign',
          status: 'executed',
          summary: 'Override executed',
          detail: {
            recommendation_id: 'cadence_overload:baseline',
            detail: { execution_hash: 'hash-1' },
          },
          actor: null,
          lineage: null,
        },
      ],
      next_cursor: null,
    }

    client.setQueryData(
      ['experiment-console', 'governance-timeline', 'exec-1', 20],
      page,
    )

    renderHook(() => useGovernanceStream('exec-1', { eventSourceFactory }), { wrapper })

    act(() => {
      mockSource.emit({
        type: 'snapshot',
        execution_id: 'exec-1',
        locks: [
          {
            override_id: 'override-1',
            recommendation_id: 'cadence_overload:baseline',
            execution_id: 'exec-1',
            execution_hash: 'hash-1',
            lock: {
              token: 'lock-123',
              actor: { id: 'user-1', name: 'Ops Lead', email: 'ops@example.com' },
              escalation_prompt: 'Override Actor lock engaged',
            },
            cooldown: { expires_at: null, remaining_seconds: 90, window_minutes: 30 },
          },
        ],
      })
    })

    const updated = client.getQueryData<GovernanceDecisionTimelinePage>([
      'experiment-console',
      'governance-timeline',
      'exec-1',
      20,
    ])

    expect(updated?.entries[0].live_state?.lock?.actor?.name).toBe('Ops Lead')
    expect(updated?.entries[0].live_state?.cooldown?.remaining_seconds).toBe(90)
  })

  it('updates cooldown ticks without resetting lock metadata', () => {
    const client = new QueryClient()
    const wrapper = createWrapper(client)
    const mockSource = new MockEventSource('/api/experiment-console/governance/timeline/stream')
    const eventSourceFactory = vi.fn(() => mockSource as unknown as EventSource)

    const basePage: GovernanceDecisionTimelinePage = {
      entries: [
        {
          entry_id: 'event-1',
          entry_type: 'override_action',
          occurred_at: new Date().toISOString(),
          execution_id: 'exec-1',
          baseline_id: null,
          rule_key: 'cadence_overload',
          action: 'reassign',
          status: 'executed',
          summary: 'Override executed',
          detail: {
            recommendation_id: 'cadence_overload:baseline',
            detail: { execution_hash: 'hash-2' },
          },
          actor: null,
          lineage: null,
        },
      ],
      next_cursor: null,
    }

    client.setQueryData(
      ['experiment-console', 'governance-timeline', 'exec-1', 20],
      basePage,
    )

    renderHook(() => useGovernanceStream('exec-1', { eventSourceFactory }), { wrapper })

    act(() => {
      mockSource.emit({
        type: 'snapshot',
        execution_id: 'exec-1',
        locks: [
          {
            override_id: 'override-2',
            recommendation_id: 'cadence_overload:baseline',
            execution_id: 'exec-1',
            execution_hash: 'hash-2',
            lock: {
              token: 'lock-789',
              actor: { id: 'user-2', name: 'Safety Lead', email: 'safety@example.com' },
            },
            cooldown: { expires_at: null, remaining_seconds: 120, window_minutes: 30 },
          },
        ],
      })
    })

    act(() => {
      mockSource.emit({
        type: 'cooldown_tick',
        execution_id: 'exec-1',
        cooldowns: [
          { override_id: 'override-2', remaining_seconds: 15, expires_at: null },
        ],
      })
    })

    const updated = client.getQueryData<GovernanceDecisionTimelinePage>([
      'experiment-console',
      'governance-timeline',
      'exec-1',
      20,
    ])

    expect(updated?.entries[0].live_state?.lock?.token).toBe('lock-789')
    expect(updated?.entries[0].live_state?.cooldown?.remaining_seconds).toBe(15)
  })
})
