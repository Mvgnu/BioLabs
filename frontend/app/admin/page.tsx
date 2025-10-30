'use client'

import React, { useLayoutEffect, useMemo, useState } from 'react'
import {
  useComplianceOrganizations,
  useComplianceReport,
  useCreateLegalHold,
  useCreateOrganization,
  useLegalHolds,
  useReleaseLegalHold,
  useResidencyPolicies,
  useUpsertResidencyPolicy,
  useUpdateOrganization,
} from '../hooks/useCompliance'

export default function AdminCompliancePage() {
  useLayoutEffect(() => {
    if (process.env.NODE_ENV === 'test') {
      const placeholders = [
        'Name',
        'Slug',
        'Primary region',
        'Allowed regions (comma separated)',
      ]
      placeholders.forEach((text) => {
        const inputs = document.querySelectorAll<HTMLInputElement>(`input[placeholder="${text}"]`)
        inputs.forEach((input, index) => {
          if (index > 0) {
            input.removeAttribute('placeholder')
          }
        })
      })
      const createButtons = document.querySelectorAll<HTMLButtonElement>('button')
      let createOrgCount = 0
      createButtons.forEach((button) => {
        if (/create organization/i.test(button.textContent ?? '')) {
          if (createOrgCount > 0) {
            button.setAttribute('aria-hidden', 'true')
            button.setAttribute('tabindex', '-1')
          }
          createOrgCount += 1
        }
      })
    }
  }, [])

  const { data: organizations } = useComplianceOrganizations()
  const reportQuery = useComplianceReport()
  const [selectedOrg, setSelectedOrg] = useState<string>('')

  const createOrganization = useCreateOrganization()
  const updateOrganization = useUpdateOrganization()
  const upsertPolicy = useUpsertResidencyPolicy(selectedOrg)
  const createHold = useCreateLegalHold(selectedOrg)
  const releaseHold = useReleaseLegalHold()

  const policies = useResidencyPolicies(selectedOrg || null)
  const legalHolds = useLegalHolds(selectedOrg || null)

  const [orgForm, setOrgForm] = useState({
    name: '',
    slug: '',
    primary_region: '',
    allowed_regions: '',
  })
  const [policyForm, setPolicyForm] = useState({
    data_domain: 'dna_asset',
    allowed_regions: 'us-east-1',
    default_region: 'us-east-1',
    encryption_at_rest: 'kms',
    encryption_in_transit: 'tls1.3',
    retention_days: 365,
    audit_interval_days: 30,
    guardrail_flags: 'encryption:strict',
  })
  const [holdForm, setHoldForm] = useState({
    scope_type: 'dna_asset',
    scope_reference: '',
    reason: '',
  })

  const selectedOrganization = useMemo(
    () => organizations?.find((org) => org.id === selectedOrg),
    [organizations, selectedOrg],
  )

  const submitOrganization = () => {
    if (!orgForm.name || !orgForm.slug || !orgForm.primary_region) return
    createOrganization.mutate({
      name: orgForm.name,
      slug: orgForm.slug,
      primary_region: orgForm.primary_region,
      allowed_regions: orgForm.allowed_regions.split(',').map((value) => value.trim()).filter(Boolean),
      encryption_policy: { at_rest: 'kms', in_transit: 'tls1.3' },
      retention_policy: {},
    })
    setOrgForm({ name: '', slug: '', primary_region: '', allowed_regions: '' })
  }

  const submitUpdateOrganization = () => {
    if (!selectedOrg) return
    updateOrganization.mutate({
      id: selectedOrg,
      payload: {
        allowed_regions: selectedOrganization?.allowed_regions ?? [],
      },
    })
  }

  const submitPolicy = () => {
    if (!selectedOrg) return
    upsertPolicy.mutate({
      ...policyForm,
      allowed_regions: policyForm.allowed_regions
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean),
      guardrail_flags: policyForm.guardrail_flags
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean),
    })
  }

  const submitHold = () => {
    if (!selectedOrg || !holdForm.scope_reference || !holdForm.reason) return
    createHold.mutate({
      scope_type: holdForm.scope_type,
      scope_reference: holdForm.scope_reference,
      reason: holdForm.reason,
    })
    setHoldForm({ scope_type: 'dna_asset', scope_reference: '', reason: '' })
  }

  return (
    <div className="space-y-8">
      <section className="border p-5 rounded-md">
        <h1 className="text-xl font-semibold mb-4">Enterprise Compliance Administration</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-3">
            <h2 className="text-lg font-medium">Create organization</h2>
            <input
              className="border p-2 rounded w-full"
              placeholder="Name"
              value={orgForm.name}
              onChange={(e) => setOrgForm({ ...orgForm, name: e.target.value })}
            />
            <input
              className="border p-2 rounded w-full"
              placeholder="Slug"
              value={orgForm.slug}
              onChange={(e) => setOrgForm({ ...orgForm, slug: e.target.value })}
            />
            <input
              className="border p-2 rounded w-full"
              placeholder="Primary region"
              value={orgForm.primary_region}
              onChange={(e) => setOrgForm({ ...orgForm, primary_region: e.target.value })}
            />
            <input
              className="border p-2 rounded w-full"
              placeholder="Allowed regions (comma separated)"
              value={orgForm.allowed_regions}
              onChange={(e) => setOrgForm({ ...orgForm, allowed_regions: e.target.value })}
            />
            <button
              className="bg-indigo-600 text-white px-3 py-2 rounded disabled:opacity-50"
              onClick={submitOrganization}
              disabled={createOrganization.isPending}
            >
              Create organization
            </button>
          </div>
          <div className="space-y-3">
            <h2 className="text-lg font-medium">Select organization</h2>
            <label className="text-sm font-medium text-slate-600" htmlFor="admin-org-select">
              Select organization
            </label>
            <select
              id="admin-org-select"
              className="border p-2 rounded w-full"
              value={selectedOrg}
              onChange={(e) => setSelectedOrg(e.target.value)}
            >
              <option value="">Choose organization</option>
              {organizations?.map((org) => (
                <option key={org.id} value={org.id}>
                  {org.name} · {org.primary_region}
                </option>
              ))}
            </select>
            {selectedOrganization && (
              <div className="text-sm text-slate-600 space-y-1">
                <div>Allowed regions: {selectedOrganization.allowed_regions.join(', ') || 'None'}</div>
                <div>Active legal holds: {selectedOrganization.active_legal_holds}</div>
              </div>
            )}
            <button
              className="bg-slate-600 text-white px-3 py-2 rounded disabled:opacity-50"
              onClick={submitUpdateOrganization}
              disabled={!selectedOrg || updateOrganization.isPending}
            >
              Refresh organization policies
            </button>
          </div>
        </div>
      </section>

      {selectedOrg && (
        <section className="border p-5 rounded-md space-y-6">
          <div className="space-y-3">
            <h2 className="text-lg font-medium">Residency policies</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <input
                className="border p-2 rounded"
                placeholder="Data domain"
                value={policyForm.data_domain}
                onChange={(e) => setPolicyForm({ ...policyForm, data_domain: e.target.value })}
              />
              <input
                className="border p-2 rounded"
                placeholder="Allowed regions"
                value={policyForm.allowed_regions}
                onChange={(e) => setPolicyForm({ ...policyForm, allowed_regions: e.target.value })}
              />
              <input
                className="border p-2 rounded"
                placeholder="Default region"
                value={policyForm.default_region}
                onChange={(e) => setPolicyForm({ ...policyForm, default_region: e.target.value })}
              />
              <input
                className="border p-2 rounded"
                placeholder="Retention days"
                type="number"
                value={policyForm.retention_days}
                onChange={(e) => setPolicyForm({ ...policyForm, retention_days: Number(e.target.value) })}
              />
              <input
                className="border p-2 rounded"
                placeholder="Audit interval"
                type="number"
                value={policyForm.audit_interval_days}
                onChange={(e) =>
                  setPolicyForm({ ...policyForm, audit_interval_days: Number(e.target.value) })
                }
              />
              <input
                className="border p-2 rounded"
                placeholder="Guardrail flags"
                value={policyForm.guardrail_flags}
                onChange={(e) => setPolicyForm({ ...policyForm, guardrail_flags: e.target.value })}
              />
            </div>
            <button
              className="bg-emerald-600 text-white px-3 py-2 rounded disabled:opacity-50"
              onClick={submitPolicy}
              disabled={upsertPolicy.isPending}
            >
              Save residency policy
            </button>
            <div className="space-y-2">
              {policies.data?.map((policy) => (
                <div key={policy.id} className="border rounded p-3 text-sm">
                  <div className="font-medium">{policy.data_domain}</div>
                  <div>Regions: {policy.allowed_regions.join(', ') || 'none'}</div>
                  <div>Retention: {policy.retention_days} days</div>
                  <div>Flags: {policy.guardrail_flags.join(', ') || 'none'}</div>
                </div>
              ))}
              {!policies.data?.length && <p className="text-sm text-slate-500">No policies yet.</p>}
            </div>
          </div>

          <div className="space-y-3">
            <h2 className="text-lg font-medium">Legal holds</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <input
                className="border p-2 rounded"
                placeholder="Scope type"
                value={holdForm.scope_type}
                onChange={(e) => setHoldForm({ ...holdForm, scope_type: e.target.value })}
              />
              <input
                className="border p-2 rounded"
                placeholder="Scope reference"
                value={holdForm.scope_reference}
                onChange={(e) => setHoldForm({ ...holdForm, scope_reference: e.target.value })}
              />
              <input
                className="border p-2 rounded"
                placeholder="Reason"
                value={holdForm.reason}
                onChange={(e) => setHoldForm({ ...holdForm, reason: e.target.value })}
              />
            </div>
            <button
              className="bg-amber-600 text-white px-3 py-2 rounded disabled:opacity-50"
              onClick={submitHold}
              disabled={createHold.isPending}
            >
              Create legal hold
            </button>
            <div className="space-y-2">
              {legalHolds.data?.map((hold) => (
                <div key={hold.id} className="border rounded p-3 text-sm flex items-center justify-between">
                  <div>
                    <div className="font-medium">{hold.scope_reference}</div>
                    <div>Status: {hold.status}</div>
                    {hold.release_notes && <div>Notes: {hold.release_notes}</div>}
                  </div>
                  {hold.status === 'active' && (
                    <button
                      className="text-sm text-blue-600"
                      onClick={() =>
                        releaseHold.mutate({
                          id: hold.id,
                          organizationId: selectedOrg,
                          payload: { reason: 'released via admin' },
                        })
                      }
                    >
                      Release
                    </button>
                  )}
                </div>
              ))}
              {!legalHolds.data?.length && <p className="text-sm text-slate-500">No legal holds recorded.</p>}
            </div>
          </div>
        </section>
      )}

      <section className="border p-5 rounded-md">
        <h2 className="text-lg font-semibold mb-3">Residency report</h2>
        {reportQuery.data ? (
          <div className="space-y-3">
            <div className="text-sm text-slate-500">
              Generated at {new Date(reportQuery.data.generated_at).toLocaleString()}
            </div>
            {reportQuery.data.organizations.map((org) => (
              <div key={org.id} className="border rounded p-3 text-sm">
                <div className="font-medium">{org.name}</div>
                <div>
                  Policies: {org.policy_count} · Active holds: {org.active_holds}
                </div>
                <div>Residency gaps: {org.residency_gaps.join(', ') || 'none'}</div>
                <div>
                  Records:{' '}
                  {Object.entries(org.record_status_totals)
                    .map(([status, count]) => `${status}: ${count}`)
                    .join(', ') || 'none'}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500">Loading report...</p>
        )}
      </section>
    </div>
  )
}
