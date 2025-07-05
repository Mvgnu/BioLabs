'use client'
import { useState } from 'react'
import Link from 'next/link'
import { useProtocolTemplates, useProtocolDiff } from '../../hooks/useProtocols'

export default function ProtocolDiffPage() {
  const { data: templates } = useProtocolTemplates()
  const [oldId, setOldId] = useState('')
  const [newId, setNewId] = useState('')
  const { data: diff } = useProtocolDiff(oldId || null, newId || null)

  return (
    <div>
      <h1 className="text-xl mb-4">Protocol Diff</h1>
      <div className="space-x-2">
        <select value={oldId} onChange={(e) => setOldId(e.target.value)}>
          <option value="">Old template</option>
          {templates?.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name} v{t.version}
            </option>
          ))}
        </select>
        <select value={newId} onChange={(e) => setNewId(e.target.value)}>
          <option value="">New template</option>
          {templates?.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name} v{t.version}
            </option>
          ))}
        </select>
      </div>
      {diff && <pre className="whitespace-pre mt-4 bg-gray-100 p-2">{diff}</pre>}
      <Link href="/protocols" className="text-blue-600 block mt-4">
        Back to protocols
      </Link>
    </div>
  )
}
