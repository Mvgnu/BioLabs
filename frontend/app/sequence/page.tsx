'use client'
import { useState } from 'react'
import { useAnnotateSequence } from '../hooks/useSequence'
import type { SequenceFeature } from '../types'

export default function SequencePage() {
  const annotate = useAnnotateSequence()
  const [features, setFeatures] = useState<SequenceFeature[] | null>(null)

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    annotate.mutate(file, {
      onSuccess: (data) => setFeatures(data),
    })
  }

  return (
    <div>
      <h1 className="text-xl mb-4">Sequence Annotation</h1>
      <p className="mb-2 space-x-4">
        <a href="/sequence/chromatogram" className="underline text-blue-600">Sanger chromatogram tool</a>
        <a href="/sequence/blast" className="underline text-blue-600">BLAST search tool</a>
        <a href="/sequence/jobs" className="underline text-blue-600">Analysis jobs</a>
      </p>
      <input type="file" onChange={handleFile} accept=".gb,.gbk" />
      {features && (
        <table className="mt-4 table-auto border-collapse">
          <thead>
            <tr>
              <th className="border px-2">Type</th>
              <th className="border px-2">Start</th>
              <th className="border px-2">End</th>
            </tr>
          </thead>
          <tbody>
            {features.map((f, idx) => (
              <tr key={idx}>
                <td className="border px-2">{f.type}</td>
                <td className="border px-2 text-right">{f.start}</td>
                <td className="border px-2 text-right">{f.end}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
