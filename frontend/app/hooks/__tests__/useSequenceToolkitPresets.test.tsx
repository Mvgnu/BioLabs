import React from 'react'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'

import type { SequenceToolkitPresetCatalog } from '../../types'
import { getSequenceToolkitPresets } from '../../api/sequenceToolkit'
import { useSequenceToolkitPresets } from '../useSequenceToolkitPresets'

vi.mock('../../api/sequenceToolkit', () => ({
  getSequenceToolkitPresets: vi.fn(),
}))

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

describe('useSequenceToolkitPresets', () => {
  it('fetches preset catalog data', async () => {
    const client = createClient()
    const catalog: SequenceToolkitPresetCatalog = {
      presets: [
        {
          preset_id: 'multiplex',
          name: 'Multiplex',
          description: 'Support multiplex primer design',
          metadata_tags: ['preset:multiplex'],
          recommended_use: ['Multiplex PCR'],
          notes: ['Balance ΔTm across primer sets.'],
          primer_overrides: {
            product_size_range: [80, 280],
            target_tm: 60,
            min_tm: 55,
            max_tm: 65,
            min_size: 18,
            opt_size: 22,
            max_size: 30,
            num_return: 1,
            na_concentration_mM: 50,
            primer_concentration_nM: 500,
            gc_clamp_min: 1,
            gc_clamp_max: 2,
          },
          restriction_overrides: {
            enzymes: ['EcoRI', 'BamHI'],
            require_all: false,
            reaction_buffer: 'CutSmart',
          },
          assembly_overrides: {
            strategy: 'gibson',
            base_success: 0.85,
            tm_penalty_factor: 0.1,
            minimal_site_count: 2,
            low_site_penalty: 0.4,
            ligation_efficiency: 0.9,
            kinetics_model: 'default',
            overlap_optimum: 26,
            overlap_tolerance: 8,
            overhang_diversity_factor: null,
          },
        },
      ],
      count: 1,
      generated_at: new Date().toISOString(),
    }
    ;(getSequenceToolkitPresets as ReturnType<typeof vi.fn>).mockResolvedValue(catalog)

    const { result } = renderHook(() => useSequenceToolkitPresets(), { wrapper: wrapper(client) })

    await waitFor(() => expect(result.current.isLoading).toBe(false))
    expect(result.current.data?.count).toBe(1)
    expect(result.current.data?.presets[0].preset_id).toBe('multiplex')
  })
})
