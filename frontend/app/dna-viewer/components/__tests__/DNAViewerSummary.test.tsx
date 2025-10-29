import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { DNAViewerPayload } from '../../../types'
import { DNAViewerSummary } from '../DNAViewerSummary'

// purpose: verify DNA viewer summary renders guardrail badges and diff metrics
// status: experimental

const samplePayload = (): DNAViewerPayload => ({
  asset: {
    id: 'asset-1',
    name: 'Sample plasmid',
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
    version_index: 2,
    sequence_length: 60,
    gc_content: 0.52,
    created_at: '2024-01-02T00:00:00.000Z',
    created_by_id: 'user-1',
    metadata: { topology: 'circular' },
    annotations: [
      {
        id: 'ann-1',
        label: 'example_cds',
        feature_type: 'CDS',
        start: 1,
        end: 30,
        strand: 1,
        qualifiers: {},
      },
    ],
    kinetics_summary: {
      enzymes: ['EcoRI'],
      buffers: ['CutSmart'],
      ligation_profiles: ['Gibson'],
      metadata_tags: ['synthetic'],
    },
    assembly_presets: ['Gibson'],
    guardrail_heuristics: {
      primers: { primer_state: 'review', metadata_tags: ['high_tm'] },
      restriction: { restriction_state: 'ok', metadata_tags: [] },
      assembly: { assembly_state: 'ok', metadata_tags: [] },
    },
  },
  sequence: 'ATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCATGCAT',
  topology: 'circular',
  tracks: [
    {
      name: 'Annotations',
      features: [
        {
          label: 'example_cds',
          feature_type: 'CDS',
          start: 1,
          end: 30,
          strand: 1,
          qualifiers: {},
          guardrail_badges: ['primer-review', 'primer-tag:high_tm'],
        },
      ],
    },
    {
      name: 'Guardrails',
      features: [
        {
          label: 'Primer Guardrails',
          feature_type: 'guardrail.primer',
          start: 1,
          end: 60,
          strand: null,
          qualifiers: { primer_state: 'review' },
          guardrail_badges: ['review'],
        },
      ],
    },
  ],
  translations: [
    { label: 'example_cds', frame: 1, sequence: 'ATGCATGCA', amino_acids: 'MHM' },
  ],
  kinetics_summary: {
    enzymes: ['EcoRI'],
    buffers: ['CutSmart'],
    ligation_profiles: ['Gibson'],
    metadata_tags: ['synthetic'],
  },
  guardrails: {
    primers: { primer_state: 'review' },
    restriction: { restriction_state: 'ok' },
    assembly: { assembly_state: 'ok' },
  },
  diff: {
    from_version: {
      id: 'version-0',
      version_index: 1,
      sequence_length: 60,
      gc_content: 0.5,
      created_at: '2024-01-01T00:00:00.000Z',
      created_by_id: 'user-1',
      metadata: {},
      annotations: [],
      kinetics_summary: {
        enzymes: [],
        buffers: [],
        ligation_profiles: [],
        metadata_tags: [],
      },
      assembly_presets: [],
      guardrail_heuristics: { primers: {}, restriction: {}, assembly: {} },
    },
    to_version: {
      id: 'version-1',
      version_index: 2,
      sequence_length: 60,
      gc_content: 0.52,
      created_at: '2024-01-02T00:00:00.000Z',
      created_by_id: 'user-1',
      metadata: {},
      annotations: [],
      kinetics_summary: {
        enzymes: [],
        buffers: [],
        ligation_profiles: [],
        metadata_tags: [],
      },
      assembly_presets: [],
      guardrail_heuristics: { primers: {}, restriction: {}, assembly: {} },
    },
    substitutions: 2,
    insertions: 1,
    deletions: 0,
    gc_delta: 0.02,
  },
})

describe('DNAViewerSummary', () => {
  it('renders guardrail badges and diff metrics', () => {
    render(<DNAViewerSummary payload={samplePayload()} />)

    expect(screen.getByText('Sample plasmid')).toBeTruthy()
    expect(screen.getByText('Primer design')).toBeTruthy()
    expect(screen.getByText('Review')).toBeTruthy()
    expect(screen.getByText('Guardrail review pending')).toBeTruthy()
    expect(screen.getByText(/Translations/)).toBeTruthy()
    expect(screen.getByText(/Version diff/)).toBeTruthy()
    expect(screen.getByText('Substitutions')).toBeTruthy()
    expect(screen.getByText('2')).toBeTruthy()
  })
})
