import { fireEvent, render, screen } from '@testing-library/react'
import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CommunityDiscoveryPage from '../page'
import type {
  CommunityFeedEntry,
  CommunityPortfolio,
  CommunityTrending,
} from '../../types'

vi.mock('../../store/useAuth', () => ({
  useAuthStore: () => ({ token: 'test-token' }),
}))

const hookMocks = vi.hoisted(() => ({
  useCommunityFeed: vi.fn(),
  useCommunityPortfolios: vi.fn(),
  useTrendingPortfolios: vi.fn(),
  useCreatePortfolio: vi.fn(),
  useRecordPortfolioEngagement: vi.fn(),
}))

vi.mock('../../hooks/useCommunity', () => hookMocks)

describe('CommunityDiscoveryPage', () => {
  const mutateCreate = vi.fn()
  const mutateEngagement = vi.fn()

  const samplePortfolio: CommunityPortfolio = {
    id: 'portfolio-1',
    slug: 'synthetic-kit',
    title: 'Synthetic kit',
    summary: 'Replay-ready qPCR assets',
    visibility: 'public',
    license: 'CC-BY-4.0',
    tags: ['qpcr', 'guardrail'],
    attribution: { authors: ['Team A'] },
    provenance: { dna_assets: [{ id: 'asset-1' }] },
    mitigation_history: [{ event_type: 'safety.review' }],
    replay_checkpoints: [{ checkpoint: 'stage-1' }],
    guardrail_flags: [],
    engagement_score: 1.6,
    status: 'published',
    published_at: new Date('2024-01-01T00:00:00Z').toISOString(),
    created_at: new Date('2023-12-31T23:00:00Z').toISOString(),
    updated_at: new Date('2024-01-01T01:00:00Z').toISOString(),
    assets: [
      {
        id: 'asset-link-1',
        asset_type: 'dna_asset',
        asset_id: 'asset-1',
        asset_version_id: 'version-1',
        planner_session_id: null,
        meta: { diff: '+A→T' },
        guardrail_snapshot: { guardrail_flags: [] },
        created_at: new Date('2024-01-01T00:00:00Z').toISOString(),
      },
    ],
  }

  const feedEntries: CommunityFeedEntry[] = [
    {
      portfolio: samplePortfolio,
      reason: 'recommended',
      score: 1.6,
    },
  ]

  const trending: CommunityTrending = {
    timeframe: '7d',
    portfolios: [
      {
        portfolio: samplePortfolio,
        engagement_delta: 2.5,
        guardrail_summary: [],
      },
    ],
  }

  beforeEach(() => {
    mutateCreate.mockReset()
    mutateEngagement.mockReset()

    hookMocks.useCommunityPortfolios.mockReturnValue({ data: [samplePortfolio] })
    hookMocks.useCommunityFeed.mockReturnValue({ data: feedEntries })
    hookMocks.useTrendingPortfolios.mockReturnValue({ data: trending })
    hookMocks.useCreatePortfolio.mockReturnValue({ mutate: mutateCreate, isPending: false })
    hookMocks.useRecordPortfolioEngagement.mockReturnValue({ mutate: mutateEngagement })
  })

  it('renders discovery panels and portfolio cards', () => {
    render(<CommunityDiscoveryPage />)
    expect(screen.getByText('Community discovery hub')).toBeTruthy()
    expect(screen.getByText('Personalized review queue')).toBeTruthy()
    expect(screen.getByText('Trending guardrail-ready releases')).toBeTruthy()
    expect(screen.getAllByText('Synthetic kit').length).toBeGreaterThan(0)
    expect(screen.getByText('guardrails cleared')).toBeTruthy()
  })

  it('submits new portfolio form', () => {
    render(<CommunityDiscoveryPage />)
    const slugInput = screen.getByLabelText('New portfolio slug') as HTMLInputElement
    fireEvent.change(slugInput, { target: { value: 'new-portfolio' } })
    const titleInput = screen.getByLabelText('Title') as HTMLInputElement
    fireEvent.change(titleInput, { target: { value: 'New portfolio' } })
    const button = screen.getAllByRole('button', { name: /Publish discovery portfolio/i })[0]
    fireEvent.click(button)
    expect(mutateCreate).toHaveBeenCalled()
  })

  it('records engagement when star button clicked', () => {
    render(<CommunityDiscoveryPage />)
    const starButton = screen.getAllByRole('button', { name: /Star for curation/i })[0]
    fireEvent.click(starButton)
    expect(mutateEngagement).toHaveBeenCalledWith({ interaction: 'star', weight: undefined })
  })
})
