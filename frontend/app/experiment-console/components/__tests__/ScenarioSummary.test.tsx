import { render, screen, within } from '@testing-library/react'
import React from 'react'
import { describe, expect, it } from 'vitest'
import ScenarioSummary from '../ScenarioSummary'
import type {
  ExperimentScenario,
  ExperimentScenarioSnapshot,
} from '../../../types'

describe('ScenarioSummary', () => {
  const baseScenario: ExperimentScenario = {
    id: 'scenario-1',
    execution_id: 'exec-1',
    owner_id: 'user-1',
    team_id: null,
    workflow_template_snapshot_id: 'snapshot-1',
    name: 'Baseline Stress Test',
    description: 'Evaluate extended SLA impact',
    resource_overrides: {
      inventory_item_ids: ['inv-1', 'inv-2'],
      booking_ids: ['book-1'],
      equipment_ids: [],
    },
    stage_overrides: [
      {
        index: 0,
        sla_hours: 72,
        assignee_id: 'scientist-1',
        delegate_id: null,
      },
    ],
    cloned_from_id: null,
    folder_id: null,
    is_shared: false,
    shared_team_ids: [],
    expires_at: null,
    timeline_event_id: null,
    created_at: new Date('2024-01-01T12:00:00Z').toISOString(),
    updated_at: new Date('2024-01-02T12:00:00Z').toISOString(),
  }

  const snapshot: ExperimentScenarioSnapshot = {
    id: 'snapshot-1',
    template_id: 'template-1',
    template_key: 'governance.baseline',
    template_name: 'Baseline Ladder',
    version: 2,
    status: 'published',
    captured_at: new Date('2024-01-01T08:00:00Z').toISOString(),
    captured_by_id: 'user-1',
  }

  it('renders scenario metadata and overrides', () => {
    render(<ScenarioSummary scenario={baseScenario} snapshot={snapshot} folderName="Unfiled" />)

    const summary = screen.getAllByTestId('scenario-summary-card')[0]
    const scoped = within(summary)

    expect(scoped.getByRole('heading', { level: 3, name: 'Baseline Stress Test' })).toBeTruthy()
    expect(scoped.getByText('Evaluate extended SLA impact')).toBeTruthy()
    expect(scoped.getByText(/Baseline Ladder · v2/)).toBeTruthy()
    expect(scoped.getByText(/Stage overrides: 1/)).toBeTruthy()
    expect(scoped.getByText(/Inventory: 2/)).toBeTruthy()
    expect(scoped.getByText(/Bookings: 1/)).toBeTruthy()
    expect(scoped.getByText(/Equipment: 0/)).toBeTruthy()
    expect(scoped.getByText(/Stage 1 · SLA 72h · Assignee scientist-1/)).toBeTruthy()
  })

  it('includes a deep link to the experiment console', () => {
    render(<ScenarioSummary scenario={baseScenario} snapshot={snapshot} folderName="Unfiled" />)
    const summary = screen.getAllByTestId('scenario-summary-card')[0]
    const link = within(summary).getByRole('link', { name: /open scenario/i }) as HTMLAnchorElement
    expect(link.getAttribute('href')).toBe('/experiment-console/exec-1?scenario=scenario-1')
  })

  it('highlights shared metadata and timeline anchors when provided', () => {
    const sharedScenario: ExperimentScenario = {
      ...baseScenario,
      id: 'scenario-2',
      name: 'Shared Scenario',
      folder_id: 'folder-1',
      is_shared: true,
      shared_team_ids: ['team-1', 'team-2'],
      expires_at: new Date('2024-02-01T12:00:00Z').toISOString(),
      timeline_event_id: 'event-123',
    }

    render(
      <ScenarioSummary
        scenario={sharedScenario}
        snapshot={snapshot}
        folderName="Team Reviews"
      />,
    )

    const cards = screen.getAllByTestId('scenario-summary-card')
    const summary = cards[cards.length - 1]
    const scoped = within(summary)

    expect(scoped.getByText((content) => content.includes('Team Reviews'))).toBeTruthy()
    expect(scoped.getByText('Shared')).toBeTruthy()
    expect(scoped.getByText(/Teams: team-1, team-2/)).toBeTruthy()
    expect(scoped.getByText(/Timeline anchor linked/)).toBeTruthy()
  })
})
