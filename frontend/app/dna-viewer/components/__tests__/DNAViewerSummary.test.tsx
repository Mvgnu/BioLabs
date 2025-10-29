import React from 'react'
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { DNAViewerPayload } from '../../../types'
import { DNAViewerSummary } from '../DNAViewerSummary'

vi.mock('../../../hooks/useLifecycleNarrative', () => ({
  useLifecycleSummary: () => ({
    data: {
      total_events: 4,
      open_escalations: 1,
      active_guardrails: 2,
      latest_event_at: '2024-01-03T05:00:00.000Z',
      custody_state: 'alert',
      context_chips: [],
    },
    isLoading: false,
  }),
  useLifecycleTimeline: () => ({
    data: {
      scope: {},
      summary: {
        total_events: 4,
        open_escalations: 1,
        active_guardrails: 2,
        latest_event_at: '2024-01-03T05:00:00.000Z',
        custody_state: 'alert',
        context_chips: [],
      },
      entries: [],
    },
    isLoading: false,
  }),
  useLifecycleNarrative: () => ({
    data: {
      summary: {
        total_events: 3,
        open_escalations: 0,
        active_guardrails: 1,
        latest_event_at: '2024-01-03T05:00:00.000Z',
        custody_state: 'review',
        context_chips: [],
      },
      entries: [
        {
          entry_id: 'entry-1',
          source: 'planner',
          event_type: 'resume',
          occurred_at: '2024-01-03T05:00:00.000Z',
          title: 'Planner resumed',
          summary: 'Planner resumed from custody gate',
          metadata: { guardrail_flags: ['custody'] },
        },
      ],
    },
    isLoading: false,
    isError: false,
  }),
}))

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
        segments: [{ start: 1, end: 30, strand: 1 }],
        provenance_tags: ['cds'],
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
    toolkit_recommendations: {
      scorecard: {
        preset_id: 'multiplex',
        preset_name: 'Multiplex',
        recommended_buffers: ['CutSmart'],
        compatibility_index: 0.87,
        multiplex_risk: 'moderate',
        primer_window: { min_tm: 58.1, max_tm: 62.3 },
      },
      strategy_scores: [
        { strategy: 'Golden Gate', compatibility: 0.87 },
        { strategy: 'Gibson', compatibility: 0.82 },
      ],
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
          segments: [{ start: 1, end: 30, strand: 1 }],
          provenance_tags: ['cds'],
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
          segments: [{ start: 1, end: 60, strand: null }],
          provenance_tags: ['guardrail.primer'],
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
  toolkit_recommendations: {
    scorecard: {
      preset_id: 'multiplex',
      preset_name: 'Multiplex',
      recommended_buffers: ['CutSmart'],
      compatibility_index: 0.87,
      multiplex_risk: 'moderate',
      primer_window: { min_tm: 58.1, max_tm: 62.3 },
    },
    strategy_scores: [
      { strategy: 'Golden Gate', compatibility: 0.87 },
      { strategy: 'Gibson', compatibility: 0.82 },
    ],
  },
  analytics: {
    codon_usage: { ATG: 0.5, TTT: 0.5 },
    gc_skew: [0.2, -0.1],
    thermodynamic_risk: { overall_state: 'review', homopolymers: [] },
    translation_frames: { counts: { '+1': 1 }, utilisation: { '+1': 1 }, active_labels: ['example_cds'] },
    codon_adaptation_index: 0.8,
    motif_hotspots: [],
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
      toolkit_recommendations: { scorecard: {}, strategy_scores: [] },
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
      toolkit_recommendations: { scorecard: {}, strategy_scores: [] },
    },
    substitutions: 2,
    insertions: 1,
    deletions: 0,
    gc_delta: 0.02,
  },
  governance_context: {
    lineage: [],
    guardrail_history: [],
    regulatory_feature_density: null,
    mitigation_playbooks: ['Primer SOP'],
    custody_ledger: [
      {
        id: 'log-1',
        performed_at: '2024-01-03T00:00:00.000Z',
        custody_action: 'deposit',
        quantity: 2,
        quantity_units: 'vials',
        compartment_label: 'Freezer A',
        guardrail_flags: ['warning'],
        planner_session_id: 'planner-1',
        branch_id: 'branch-1',
        performed_by_id: null,
        performed_for_team_id: null,
        notes: 'Initial deposit',
        metadata: { severity: 'review' },
      },
    ],
    custody_escalations: [
      {
        id: 'esc-1',
        severity: 'review',
        status: 'open',
        reason: 'temperature',
        created_at: '2024-01-03T05:00:00.000Z',
        due_at: '2024-01-04T00:00:00.000Z',
        acknowledged_at: null,
        resolved_at: null,
        assigned_to_id: null,
        planner_session_id: 'planner-1',
        asset_version_id: 'version-1',
        guardrail_flags: ['temp'],
        metadata: {},
      },
    ],
    timeline: [
      {
        id: 'tl-1',
        timestamp: '2024-01-03T05:00:00.000Z',
        source: 'custody_log',
        title: 'Custody deposit',
        severity: 'review',
        details: { branch_id: 'branch-1' },
      },
    ],
    planner_sessions: [
      {
        session_id: 'planner-1',
        status: 'halted',
        guardrail_gate: 'custody',
        custody_status: 'halted',
        active_branch_id: 'branch-1',
        branch_order: ['branch-1'],
        replay_window: { resume_token: { stage: 'qc_recovery' } },
        recovery_context: { custody: { recovery_gate: true } },
        updated_at: '2024-01-03T05:00:00.000Z',
      },
    ],
    sop_links: ['https://example.com/sop'],
  },
})

describe('DNAViewerSummary', () => {
  it('renders guardrail badges and diff metrics', () => {
    render(<DNAViewerSummary payload={samplePayload()} />)

    expect(screen.getByText('Sample plasmid')).toBeTruthy()
    expect(screen.getByText('Primer design')).toBeTruthy()
    expect(screen.getByText('Review')).toBeTruthy()
    expect(screen.getByText('Guardrail review pending')).toBeTruthy()
    expect(screen.getByText('Toolkit strategies')).toBeTruthy()
    expect(screen.getByText('Multiplex')).toBeTruthy()
    expect(screen.getByText('Recommended buffers')).toBeTruthy()
    expect(screen.getByText('Golden Gate')).toBeTruthy()
    expect(screen.getByText('Custody escalation: temperature')).toBeTruthy()
    expect(screen.getByText('Governance timeline')).toBeTruthy()
    expect(screen.getByText('Custody ledger')).toBeTruthy()
    expect(screen.getByText('Planner branch context')).toBeTruthy()
    expect(screen.getByText('Governance playbooks & SOPs')).toBeTruthy()
    expect(screen.getByTestId('lifecycle-summary-panel')).toBeTruthy()
    expect(screen.getByText('Custody deposit')).toBeTruthy()
    expect(screen.getByText(/Translations/)).toBeTruthy()
    expect(screen.getByText(/Version diff/)).toBeTruthy()
    expect(screen.getByText('Substitutions')).toBeTruthy()
    expect(screen.getAllByText('2')[0]).toBeTruthy()
    expect(screen.getByRole('button', { name: /analytics overlays/i })).toBeTruthy()
  })
})
