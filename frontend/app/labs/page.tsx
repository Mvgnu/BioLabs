'use client'
import { useState } from 'react'
import {
  useLabs,
  useCreateLab,
  useConnections,
  useRequestConnection,
  useAcceptConnection,
} from '../hooks/useLabs'

export default function LabsPage() {
  const { data: labs } = useLabs()
  const createLab = useCreateLab()
  const { data: connections } = useConnections()
  const accept = useAcceptConnection()
  const [name, setName] = useState('')
  const [target, setTarget] = useState('')
  const [selected, setSelected] = useState<string | null>(null)

  const request = useRequestConnection(selected ?? '')

  return (
    <div>
      <h1 className="text-xl mb-4">Labs</h1>
      <div className="mb-4">
        <input className="border p-1 mr-2" value={name} onChange={(e) => setName(e.target.value)} />
        <button onClick={() => { createLab.mutate({ name }); setName('') }}>Create Lab</button>
      </div>
      <ul className="space-y-2 mb-6">
        {labs?.map((l) => (
          <li key={l.id} className="border p-2 cursor-pointer" onClick={() => setSelected(l.id)}>
            {l.name}
          </li>
        ))}
      </ul>
      {selected && (
        <div className="mb-6">
          <h2 className="text-lg mb-2">Request Connection</h2>
          <input className="border p-1 mr-2" value={target} onChange={(e) => setTarget(e.target.value)} placeholder="Target Lab ID" />
          <button onClick={() => { request.mutate(target); setTarget('') }}>Send</button>
        </div>
      )}
      <h2 className="text-lg mb-2">Connections</h2>
      <ul className="space-y-2">
        {connections?.map((c) => (
          <li key={c.id} className="border p-2 flex justify-between">
            <span>
              {c.from_lab} ➜ {c.to_lab} - {c.status}
            </span>
            {c.status === 'pending' && (
              <button onClick={() => accept.mutate(c.id)}>Accept</button>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
