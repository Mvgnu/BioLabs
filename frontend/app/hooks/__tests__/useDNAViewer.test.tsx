import type { ReactNode } from 'react'
import React from 'react'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi, beforeEach } from 'vitest'

import api from '../../api/client'
import type { DNAViewerPayload } from '../../types'
import { useDNAViewer } from '../useDNAViewer'

vi.mock('../../api/client', () => ({
  default: {
    get: vi.fn(),
  },
}))

// purpose: ensure dna viewer hook fetches payloads with optional comparison
// status: experimental

const withClient = (client: QueryClient) => {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
}

describe('useDNAViewer', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches viewer payloads for an asset id', async () => {
    const sample: DNAViewerPayload = {
      asset: {
        id: 'asset-1',
        name: 'Example asset',
        status: 'draft',
        team_id: null,
        created_by_id: 'user-1',
        created_at: '2024-01-01T00:00:00.000Z',
        updated_at: '2024-01-01T00:00:00.000Z',
        tags: ['circular'],
        latest_version: null,
      },
      version: {
        id: 'version-1',
        version_index: 1,
        sequence_length: 60,
        gc_content: 0.5,
        created_at: '2024-01-01T00:00:00.000Z',
        created_by_id: 'user-1',
        metadata: { topology: 'circular' },
        annotations: [
          {
            id: 'ann-1',
            label: 'feature',
            feature_type: 'CDS',
            start: 1,
            end: 30,
            strand: 1,
            qualifiers: {},
            segments: [
              { start: 1, end: 30, strand: 1 },
            ],
            provenance_tags: ['cds'],
          },
        ],
        kinetics_summary: {
          enzymes: ['EcoRI'],
          buffers: ['CutSmart'],
          ligation_profiles: ['Gibson'],
          metadata_tags: [],
        },
        assembly_presets: ['Gibson'],
        guardrail_heuristics: {
          primers: { primer_state: 'ok' },
          restriction: { restriction_state: 'ok' },
          assembly: { assembly_state: 'ok' },
        },
      },
      sequence: 'ATGC',
      topology: 'circular',
      tracks: [
        {
          name: 'Annotations',
          features: [
            {
              label: 'feature',
              feature_type: 'CDS',
              start: 1,
              end: 30,
              strand: 1,
              qualifiers: {},
              guardrail_badges: [],
              segments: [{ start: 1, end: 30, strand: 1 }],
              provenance_tags: ['cds'],
            },
          ],
        },
      ],
      translations: [],
      kinetics_summary: {
        enzymes: ['EcoRI'],
        buffers: ['CutSmart'],
        ligation_profiles: ['Gibson'],
        metadata_tags: [],
      },
      guardrails: {
        primers: { primer_state: 'ok' },
        restriction: { restriction_state: 'ok' },
        assembly: { assembly_state: 'ok' },
      },
      analytics: {
        codon_usage: { ATG: 1 },
        gc_skew: [0.1],
        thermodynamic_risk: { overall_state: 'ok' },
      },
      diff: null,
    }

    ;(api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: sample })

    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })

    const { result } = renderHook(() => useDNAViewer('asset-1'), {
      wrapper: withClient(qc),
    })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(sample)
    expect(api.get).toHaveBeenCalledWith('/api/dna-assets/asset-1/viewer', {
      params: undefined,
    })
  })

  it('passes compare version parameter when provided', async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    ;(api.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} })

    renderHook(() => useDNAViewer('asset-2', 'version-1'), {
      wrapper: withClient(qc),
    })

    await waitFor(() => expect(api.get).toHaveBeenCalled())
    expect(api.get).toHaveBeenCalledWith('/api/dna-assets/asset-2/viewer', {
      params: { compare_version: 'version-1' },
    })
  })
})
