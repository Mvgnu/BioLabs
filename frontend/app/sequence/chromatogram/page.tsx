'use client'
import { useState } from 'react'
import { useChromatogram } from '../../hooks/useSequence'
import ChromatogramPlot from '../../components/ChromatogramPlot'
import type { ChromatogramData } from '../../types'

export default function ChromatogramPage() {
  const parse = useChromatogram()
  const [data, setData] = useState<ChromatogramData | null>(null)

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    parse.mutate(file, { onSuccess: setData })
  }

  return (
    <div>
      <h1 className="text-xl mb-4">Sanger Chromatogram</h1>
      <input type="file" onChange={handleFile} accept=".ab1" />
      {data && (
        <div className="mt-4 space-y-4">
          <p>Sequence length: {data.sequence.length}</p>
          <pre className="whitespace-pre-wrap break-all">{data.sequence.slice(0,200)}</pre>
          <ChromatogramPlot data={data} height={150} />
        </div>
      )}
    </div>
  )
}
