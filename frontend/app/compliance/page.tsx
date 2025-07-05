'use client'
import { useState } from 'react'
import {
  useComplianceRecords,
  useCreateRecord,
  useUpdateRecord,
  useComplianceSummary,
} from '../hooks/useCompliance'

export default function CompliancePage() {
  const { data: records } = useComplianceRecords()
  const createRecord = useCreateRecord()
  const updateRecord = useUpdateRecord()
  const { data: summary } = useComplianceSummary()
  const [type, setType] = useState('safety')
  const [notes, setNotes] = useState('')

  const submit = () => {
    createRecord.mutate({ record_type: type, notes })
    setNotes('')
  }

  return (
    <div>
      <h1 className="text-xl mb-4">Compliance Dashboard</h1>
      <div className="mb-4 space-x-2">
        <input
          className="border p-1"
          value={type}
          onChange={(e) => setType(e.target.value)}
          placeholder="Type"
        />
        <input
          className="border p-1"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Notes"
        />
        <button className="bg-blue-500 text-white px-2" onClick={submit}>
          Add
        </button>
      </div>
      <h2 className="text-lg mb-2">Summary</h2>
      <ul className="mb-4">
        {summary?.map((s) => (
          <li key={s.status}>
            {s.status}: {s.count}
          </li>
        ))}
      </ul>
      <h2 className="text-lg mb-2">Records</h2>
      <ul className="space-y-2">
        {records?.map((r) => (
          <li key={r.id} className="border p-2 flex justify-between">
            <span>
              {r.record_type} - {r.status} {r.notes && <>({r.notes})</>}
            </span>
            {r.status !== 'approved' && (
              <button
                className="text-sm text-blue-600"
                onClick={() =>
                  updateRecord.mutate({ id: r.id, data: { status: 'approved' } })
                }
              >
                Approve
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
