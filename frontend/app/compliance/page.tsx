'use client'

import { useState } from 'react'
import {
  useComplianceOrganizations,
  useComplianceRecords,
  useComplianceSummary,
  useCreateRecord,
  useUpdateRecord,
} from '../hooks/useCompliance'

export default function CompliancePage() {
  const { data: organizations } = useComplianceOrganizations()
  const { data: records } = useComplianceRecords()
  const { data: summary } = useComplianceSummary()
  const createRecord = useCreateRecord()
  const updateRecord = useUpdateRecord()

  const [organizationId, setOrganizationId] = useState<string>('')
  const [recordType, setRecordType] = useState('guardrail')
  const [dataDomain, setDataDomain] = useState('dna_asset')
  const [region, setRegion] = useState('')
  const [notes, setNotes] = useState('')

  const submit = () => {
    if (!organizationId || !dataDomain) return
    createRecord.mutate({
      organization_id: organizationId,
      record_type: recordType,
      data_domain: dataDomain,
      region,
      notes,
      status: 'pending',
    })
    setNotes('')
  }

  return (
    <div className="space-y-6">
      <section className="border p-4 rounded-md">
        <h1 className="text-xl font-semibold mb-3">Compliance Dashboard</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <label className="flex flex-col text-sm">
            <span className="font-medium mb-1">Organization</span>
            <select
              className="border p-2 rounded"
              value={organizationId}
              onChange={(e) => setOrganizationId(e.target.value)}
            >
              <option value="">Select organization</option>
              {organizations?.map((org) => (
                <option key={org.id} value={org.id}>
                  {org.name} · {org.primary_region}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col text-sm">
            <span className="font-medium mb-1">Record type</span>
            <input
              className="border p-2 rounded"
              value={recordType}
              onChange={(e) => setRecordType(e.target.value)}
              placeholder="guardrail"
            />
          </label>
          <label className="flex flex-col text-sm">
            <span className="font-medium mb-1">Data domain</span>
            <input
              className="border p-2 rounded"
              value={dataDomain}
              onChange={(e) => setDataDomain(e.target.value)}
              placeholder="dna_asset"
            />
          </label>
          <label className="flex flex-col text-sm">
            <span className="font-medium mb-1">Region override</span>
            <input
              className="border p-2 rounded"
              value={region}
              onChange={(e) => setRegion(e.target.value)}
              placeholder="us-east-1"
            />
          </label>
          <label className="flex flex-col text-sm md:col-span-2">
            <span className="font-medium mb-1">Notes</span>
            <textarea
              className="border p-2 rounded"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Add residency evaluation notes"
            />
          </label>
        </div>
        <button
          className="mt-4 bg-blue-600 text-white px-3 py-2 rounded disabled:opacity-50"
          onClick={submit}
          disabled={!organizationId || createRecord.isPending}
        >
          Log compliance record
        </button>
      </section>

      <section className="border p-4 rounded-md">
        <h2 className="text-lg font-semibold mb-3">Summary</h2>
        <div className="flex flex-wrap gap-4">
          {summary?.map((s) => (
            <div key={s.status} className="bg-slate-100 p-3 rounded">
              <div className="text-xs uppercase tracking-wide text-slate-500">{s.status}</div>
              <div className="text-2xl font-semibold">{s.count}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="border p-4 rounded-md">
        <h2 className="text-lg font-semibold mb-3">Records</h2>
        <div className="space-y-3">
          {records?.map((record) => (
            <div key={record.id} className="border rounded p-3">
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-medium">{record.record_type}</div>
                  <div className="text-sm text-slate-500">
                    {record.data_domain} · {record.region || 'default region'}
                  </div>
                </div>
                <button
                  className="text-sm text-blue-600"
                  onClick={() =>
                    updateRecord.mutate({ id: record.id, data: { status: 'approved' } })
                  }
                >
                  Mark approved
                </button>
              </div>
              {record.notes && <p className="text-sm mt-2">{record.notes}</p>}
              <div className="text-xs text-slate-500 mt-2">
                Flags: {record.guardrail_flags.join(', ') || 'none'}
              </div>
              {record.retention_period_days && (
                <div className="text-xs text-slate-500">
                  Retention: {record.retention_period_days} days
                </div>
              )}
            </div>
          ))}
          {!records?.length && <p className="text-sm text-slate-500">No compliance records yet.</p>}
        </div>
      </section>
    </div>
  )
}
