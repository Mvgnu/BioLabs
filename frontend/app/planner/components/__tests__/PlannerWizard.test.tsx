import React from 'react'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { CloningPlannerSession } from '../../../types'
import { PlannerWizard } from '../PlannerWizard'
import { useCloningPlanner } from '../../../hooks/useCloningPlanner'
import { useSequenceToolkitPresets } from '../../../hooks/useSequenceToolkitPresets'

vi.mock('../../../hooks/useCloningPlanner')
vi.mock('../../../hooks/useSequenceToolkitPresets')

const mockedUseCloningPlanner = vi.mocked(useCloningPlanner)
const mockedUseSequenceToolkitPresets = vi.mocked(useSequenceToolkitPresets)

const sessionFixture = (): CloningPlannerSession => ({
  id: 'planner-1',
  created_by_id: 'user-1',
  status: 'ready_for_finalize',
  assembly_strategy: 'gibson',
  protocol_execution_id: null,
  input_sequences: [{ name: 'vector', sequence: 'ATGC', metadata: { length: 4 } }],
  primer_set: { primers: [] },
  restriction_digest: { digests: [] },
  assembly_plan: { steps: [] },
  qc_reports: { reports: [] },
  inventory_reservations: [],
  guardrail_state: {
    primers: { primer_state: 'review', primer_warnings: 2, metadata_tags: ['high_tm'] },
    restriction: { restriction_state: 'ok', metadata_tags: [] },
    assembly: { assembly_state: 'ok', ligations: [], metadata_tags: [] },
    qc: { qc_state: 'review', breaches: [{ metric: 'snr', value: 9.4 }], metadata_tags: [] },
  },
  guardrail_gate: { active: false, reasons: [] },
  branch_state: { branches: { 'branch-main': { id: 'branch-main', label: 'main' } }, order: ['branch-main'] },
  active_branch_id: 'branch-main',
  timeline_cursor: 'cursor-1',
  stage_timings: {
    primers: { status: 'primers_complete', retries: 1 },
    restriction: { status: 'restriction_running' },
  },
  current_step: 'restriction',
  celery_task_id: null,
  last_error: null,
  created_at: '2024-01-01T00:00:00.000Z',
  updated_at: '2024-01-01T00:00:00.000Z',
  completed_at: null,
  stage_history: [
    {
      id: 'record-1',
      stage: 'primers',
      attempt: 0,
      retry_count: 0,
      status: 'primers_complete',
      task_id: null,
      payload_path: null,
      payload_metadata: {},
      guardrail_snapshot: {},
      metrics: {},
      review_state: {},
      started_at: null,
      completed_at: '2024-01-01T00:00:00.000Z',
      error: null,
      branch_id: 'branch-main',
      checkpoint_key: 'primers',
      checkpoint_payload: { status: 'primers_complete', branch_id: 'branch-main' },
      guardrail_transition: { current: { active: false, reasons: [] }, previous: { active: false, reasons: [] } },
      timeline_position: 'cursor-1',
      created_at: '2024-01-01T00:00:00.000Z',
      updated_at: '2024-01-01T00:00:00.000Z',
    },
  ],
  qc_artifacts: [
    {
      id: 'artifact-1',
      artifact_name: 'Sample A',
      sample_id: 'sample-a',
      trace_path: null,
      storage_path: null,
      metrics: { signal_to_noise: 9.4 },
      thresholds: { signal_to_noise: 15 },
      stage_record_id: 'record-1',
      reviewer_id: null,
      reviewer_decision: null,
      reviewer_notes: null,
      reviewer_email: undefined,
      reviewer_decision_at: undefined,
      created_at: null,
      updated_at: null,
    } as any,
  ],
})

const createHookReturn = () => {
  const runStage = vi.fn()
  const resume = vi.fn()
  const finalize = vi.fn()
  const cancel = vi.fn()
  const session = sessionFixture()
  mockedUseCloningPlanner.mockReturnValue({
    data: session,
    isLoading: false,
    events: [
      {
        type: 'stage_completed',
        session_id: 'planner-1',
        status: 'ready_for_finalize',
        current_step: 'restriction',
        payload: { stage: 'primers' },
        guardrail_gate: session.guardrail_gate,
        guardrail_transition: { current: { active: false, reasons: [] }, previous: { active: false, reasons: [] } },
        branch: { active: 'branch-main' },
        timeline_cursor: 'cursor-1',
        id: 'cursor-1',
        timestamp: '2024-01-01T00:00:00.000Z',
      },
    ],
    replayWindow: session.stage_history,
    comparisonWindow: [],
    latestResumeToken: {
      session_id: 'planner-1',
      checkpoint: 'primers',
      branch_id: 'branch-main',
      timeline_cursor: 'cursor-1',
    },
    recoveryBundle: {
      stage: 'restriction',
      recommended_stage: 'restriction',
      resume_token: {
        session_id: 'planner-1',
        checkpoint: 'primers',
        branch_id: 'branch-main',
        timeline_cursor: 'cursor-1',
      },
      guardrail_reasons: [],
      resume_ready: true,
    },
    mitigationHints: [],
    runStage,
    resume,
    finalize,
    cancel,
    refetch: vi.fn(),
    isFetching: false,
    error: null,
    mutations: {
      stage: { isPending: false },
      resume: { isPending: false },
      finalize: { isPending: false },
      cancel: { isPending: false },
    },
  })
  return { runStage, resume, finalize, cancel }
}

beforeEach(() => {
  vi.clearAllMocks()
  mockedUseSequenceToolkitPresets.mockReturnValue({
    data: {
      presets: [
        {
          preset_id: 'multiplex',
          name: 'Multiplex',
          description: 'Multi-amplicon balancing',
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
        {
          preset_id: 'high_gc',
          name: 'High GC',
          description: 'Stabilise GC-heavy amplicons',
          metadata_tags: ['preset:high_gc'],
          recommended_use: ['GC-rich templates'],
          notes: ['Increase salt and clamp length.'],
          primer_overrides: {
            product_size_range: [100, 320],
            target_tm: 62,
            min_tm: 58,
            max_tm: 66,
            min_size: 20,
            opt_size: 24,
            max_size: 32,
            num_return: 2,
            na_concentration_mM: 70,
            primer_concentration_nM: 900,
            gc_clamp_min: 2,
            gc_clamp_max: 4,
          },
          restriction_overrides: {
            enzymes: ['NheI', 'XhoI'],
            require_all: false,
            reaction_buffer: 'High-GC',
          },
          assembly_overrides: {
            strategy: 'gibson',
            base_success: 0.72,
            tm_penalty_factor: 0.07,
            minimal_site_count: 2,
            low_site_penalty: 0.6,
            ligation_efficiency: 0.9,
            kinetics_model: 'high_fidelity',
            overlap_optimum: 28,
            overlap_tolerance: 8,
            overhang_diversity_factor: null,
          },
        },
      ],
      count: 2,
      generated_at: new Date().toISOString(),
    },
    isLoading: false,
  })
})

describe('PlannerWizard', () => {
  it('renders guardrail overview and event log', () => {
    createHookReturn()
    render(<PlannerWizard sessionId="planner-1" />)

    expect(screen.getByText('Cloning planner')).toBeTruthy()
    expect(screen.getAllByText('Primer design').length).toBeGreaterThan(0)
    expect(screen.getByText(/Planner guardrails require review before finalization/)).toBeTruthy()
    expect(screen.getByTestId('planner-timeline')).toBeTruthy()
  })

  it('submits stage forms with expected payloads', () => {
    const { runStage } = createHookReturn()
    render(<PlannerWizard sessionId="planner-1" />)

    const primerForm = screen.getAllByTestId('primer-stage-form')[0]
    fireEvent.change(within(primerForm).getByLabelText('Primer preset'), { target: { value: 'multiplex' } })
    fireEvent.change(within(primerForm).getByLabelText('Target Tm (°C)'), { target: { value: '62' } })
    fireEvent.change(within(primerForm).getByLabelText('Product size min'), { target: { value: '90' } })
    fireEvent.change(within(primerForm).getByLabelText('Product size max'), { target: { value: '120' } })
    fireEvent.submit(primerForm)

    expect(runStage).toHaveBeenCalledWith('primers', {
      payload: { target_tm: 62, product_size_range: [90, 120], preset_id: 'multiplex' },
    })
  })

  it('shows QC decision loop artifacts', () => {
    createHookReturn()
    render(<PlannerWizard sessionId="planner-1" />)

    const qcLoop = screen.getAllByTestId('guardrail-qc-loop')[0]
    expect(qcLoop).toBeTruthy()
    expect(within(qcLoop).getByText('Sample A')).toBeTruthy()
  })

  it('disables stage controls when guardrail gate is active', () => {
    const session = sessionFixture()
    session.guardrail_gate = { active: true, reasons: ['custody_status:halted'] }
    session.guardrail_state = {
      ...session.guardrail_state,
      custody_status: 'halted',
      custody: { open_escalations: 2, open_drill_count: 1, qc_backpressure: true },
    }
    session.stage_timings = {
      ...session.stage_timings,
      primers: { status: 'primers_guardrail_hold' },
    }
    session.branch_state = { branches: { 'branch-main': { id: 'branch-main', label: 'main' } }, order: ['branch-main'] }
    const runStage = vi.fn()
    mockedUseCloningPlanner.mockReturnValue({
      data: session,
      isLoading: false,
      events: [],
      runStage,
      resume: vi.fn(),
      finalize: vi.fn(),
      cancel: vi.fn(),
      refetch: vi.fn(),
      isFetching: false,
      error: null,
      mutations: {
        stage: { isPending: false },
        resume: { isPending: false },
        finalize: { isPending: false },
        cancel: { isPending: false },
      },
    })

    render(<PlannerWizard sessionId="planner-1" />)

    expect(screen.getByTestId('planner-guardrail-gate')).toBeTruthy()
    const resumeButtons = screen.getAllByRole('button', { name: /Resume pipeline/i })
    expect(resumeButtons.some((button) => (button as HTMLButtonElement).disabled)).toBe(true)
  })
})

