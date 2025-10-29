import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import React from 'react'
import { describe, expect, it, vi } from 'vitest'

import PlannerIntakePage from '../page'

const mocks = vi.hoisted(() => ({
  createCloningPlannerSession: vi.fn(),
  useRouter: vi.fn(),
  useSequenceToolkitPresets: vi.fn(),
}))

vi.mock('../../api/cloningPlanner', () => ({
  createCloningPlannerSession: mocks.createCloningPlannerSession,
}))

vi.mock('next/navigation', () => ({
  useRouter: mocks.useRouter,
}))

vi.mock('../../hooks/useSequenceToolkitPresets', () => ({
  useSequenceToolkitPresets: mocks.useSequenceToolkitPresets,
}))

describe('PlannerIntakePage', () => {
  it('submits intake form with selected preset', async () => {
    const push = vi.fn()
    mocks.useRouter.mockReturnValue({ push })
    mocks.useSequenceToolkitPresets.mockReturnValue({
      data: {
        presets: [
          {
            preset_id: 'multiplex',
            name: 'Multiplex',
            description: 'Balance multiplex primer sets',
            metadata_tags: ['preset:multiplex'],
            recommended_use: ['Multiplex PCR'],
            notes: ['Keep ΔTm narrow.'],
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
      },
      isLoading: false,
    })
    mocks.createCloningPlannerSession.mockResolvedValue({ id: 'planner-123' })

    render(<PlannerIntakePage />)

    const presetSelect = screen.getByLabelText('Toolkit preset')
    fireEvent.change(presetSelect, { target: { value: 'multiplex' } })

    const submitButton = screen.getByRole('button', { name: /Launch planner wizard/i })
    fireEvent.click(submitButton)

    await waitFor(() => expect(mocks.createCloningPlannerSession).toHaveBeenCalled())
    expect(mocks.createCloningPlannerSession).toHaveBeenCalledWith(
      expect.objectContaining({ toolkit_preset: 'multiplex' }),
    )
    expect(push).toHaveBeenCalledWith('/planner/planner-123')
    expect(screen.getByText('Balance multiplex primer sets')).toBeDefined()
  })
})
