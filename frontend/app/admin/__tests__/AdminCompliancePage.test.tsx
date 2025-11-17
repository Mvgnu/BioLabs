import { fireEvent, render, screen } from '@testing-library/react'
import React from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import AdminCompliancePage from '../page'
import type {
  ComplianceOrganization,
  ComplianceReportSummary,
  LegalHold,
  ResidencyPolicy,
} from '../../types'

const hookMocks = vi.hoisted(() => ({
  useComplianceOrganizations: vi.fn(),
  useComplianceReport: vi.fn(),
  useCreateLegalHold: vi.fn(),
  useCreateOrganization: vi.fn(),
  useLegalHolds: vi.fn(),
  useReleaseLegalHold: vi.fn(),
  useResidencyPolicies: vi.fn(),
  useUpsertResidencyPolicy: vi.fn(),
  useUpdateOrganization: vi.fn(),
}))

vi.mock('../../hooks/useCompliance', () => hookMocks)

describe('AdminCompliancePage', () => {
  const mutateCreateOrg = vi.fn()
  const mutateUpdateOrg = vi.fn()
  const mutatePolicy = vi.fn()
  const mutateHold = vi.fn()
  const mutateRelease = vi.fn()

  const organization: ComplianceOrganization = {
    id: 'org-1',
    name: 'Helios Labs',
    slug: 'helios',
    primary_region: 'us-east-1',
    residency_enforced: true,
    allowed_regions: ['us-east-1'],
    encryption_policy: { at_rest: 'kms' },
    retention_policy: {},
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    policy_count: 1,
    active_legal_holds: 1,
  }

  const policy: ResidencyPolicy = {
    id: 'policy-1',
    data_domain: 'dna_asset',
    allowed_regions: ['us-east-1'],
    default_region: 'us-east-1',
    encryption_at_rest: 'kms',
    encryption_in_transit: 'tls1.3',
    retention_days: 365,
    audit_interval_days: 30,
    guardrail_flags: ['encryption:strict'],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }

  const legalHold: LegalHold = {
    id: 'hold-1',
    scope_type: 'dna_asset',
    scope_reference: 'asset-1',
    reason: 'investigation',
    status: 'active',
    created_at: new Date().toISOString(),
    released_at: null,
    release_notes: null,
  }

  const report: ComplianceReportSummary = {
    generated_at: new Date().toISOString(),
    organizations: [
      {
        id: 'org-1',
        name: 'Helios Labs',
        primary_region: 'us-east-1',
        residency_enforced: true,
        policy_count: 1,
        active_holds: 1,
        residency_gaps: [],
        record_status_totals: { approved: 2 },
      },
    ],
  }

  beforeEach(() => {
    mutateCreateOrg.mockReset()
    mutateUpdateOrg.mockReset()
    mutatePolicy.mockReset()
    mutateHold.mockReset()
    mutateRelease.mockReset()

    hookMocks.useComplianceOrganizations.mockReturnValue({ data: [organization] })
    hookMocks.useComplianceReport.mockReturnValue({ data: report })
    hookMocks.useResidencyPolicies.mockReturnValue({ data: [policy] })
    hookMocks.useLegalHolds.mockReturnValue({ data: [legalHold] })
    hookMocks.useCreateOrganization.mockReturnValue({ mutate: mutateCreateOrg, isPending: false })
    hookMocks.useUpdateOrganization.mockReturnValue({ mutate: mutateUpdateOrg, isPending: false })
    hookMocks.useUpsertResidencyPolicy.mockReturnValue({ mutate: mutatePolicy, isPending: false })
    hookMocks.useCreateLegalHold.mockReturnValue({ mutate: mutateHold, isPending: false })
    hookMocks.useReleaseLegalHold.mockReturnValue({ mutate: mutateRelease })
  })

  it('renders organizations, policies, and report', () => {
    render(<AdminCompliancePage />)
    expect(screen.getByText('Enterprise Compliance Administration')).toBeTruthy()
    expect(screen.getByText('Helios Labs · us-east-1')).toBeTruthy()
    expect(screen.getByText('Residency report')).toBeTruthy()
  })

  it('submits organization creation form', () => {
    render(<AdminCompliancePage />)
    fireEvent.change(screen.getByPlaceholderText('Name'), { target: { value: 'Orion' } })
    fireEvent.change(screen.getByPlaceholderText('Slug'), { target: { value: 'orion' } })
    fireEvent.change(screen.getByPlaceholderText('Primary region'), { target: { value: 'us-west-2' } })
    fireEvent.change(screen.getByPlaceholderText('Allowed regions (comma separated)'), {
      target: { value: 'us-west-2, eu-west-1' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Create organization/i }))
    expect(mutateCreateOrg).toHaveBeenCalled()
  })

  it('saves residency policy and releases legal hold', () => {
    render(<AdminCompliancePage />)
    fireEvent.change(screen.getByRole('combobox', { name: /Select organization/i }), {
      target: { value: 'org-1' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Save residency policy/i }))
    expect(mutatePolicy).toHaveBeenCalled()

    const releaseButton = screen.getByRole('button', { name: /Release/i })
    fireEvent.click(releaseButton)
    expect(mutateRelease).toHaveBeenCalledWith({
      id: 'hold-1',
      organizationId: 'org-1',
      payload: { reason: 'released via admin' },
    })
  })

  it('creates legal hold for selected organization', () => {
    render(<AdminCompliancePage />)
    fireEvent.change(screen.getByRole('combobox', { name: /Select organization/i }), {
      target: { value: 'org-1' },
    })
    fireEvent.change(screen.getByPlaceholderText('Scope reference'), {
      target: { value: 'asset-99' },
    })
    fireEvent.change(screen.getByPlaceholderText('Reason'), { target: { value: 'audit' } })
    fireEvent.click(screen.getByRole('button', { name: /Create legal hold/i }))
    expect(mutateHold).toHaveBeenCalledWith({
      scope_type: 'dna_asset',
      scope_reference: 'asset-99',
      reason: 'audit',
    })
  })
})
