'use client'
import { useState } from 'react'
import { useBlastSearch } from '../../hooks/useSequence'
import type { BlastResult } from '../../types'

export default function BlastPage() {
  const blast = useBlastSearch()
  const [query, setQuery] = useState('')
  const [subject, setSubject] = useState('')
  const [result, setResult] = useState<BlastResult | null>(null)

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    blast.mutate({ query, subject }, { onSuccess: setResult })
  }

  return (
    <div>
      <h1 className="text-xl mb-4">BLAST Search</h1>
      <form onSubmit={handleSubmit} className="space-y-2 mb-4">
        <div>
          <label className="block font-semibold mb-1">Query Sequence</label>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="border p-1 w-full"
            rows={4}
          />
        </div>
        <div>
          <label className="block font-semibold mb-1">Subject Sequence</label>
          <textarea
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            className="border p-1 w-full"
            rows={4}
          />
        </div>
        <button type="submit" className="bg-blue-500 text-white px-2 py-1">
          Search
        </button>
      </form>
      {result && (
        <div className="text-sm mt-4">
          <p>Score: {result.score.toFixed(2)}</p>
          <p>Identity: {result.identity.toFixed(2)}%</p>
          <pre className="whitespace-pre-wrap break-all mt-2">
            {result.query_aligned}
            {'\n'}
            {result.subject_aligned}
          </pre>
        </div>
      )}
    </div>
  )
}
