'use client'
import { useState } from 'react'
import { useCreateSequenceJob, useSequenceJobs } from '../../hooks/useSequence'
import type { SequenceJob } from '../../types'

export default function SequenceJobsPage() {
  const [file, setFile] = useState<File | null>(null)
  const [format, setFormat] = useState('fasta')
  const create = useCreateSequenceJob()
  const { data: jobs } = useSequenceJobs()

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    if (!file) return
    create.mutate({ file, format })
  }

  return (
    <div>
      <h1 className="text-xl mb-4">Sequence Analysis Jobs</h1>
      <form onSubmit={handleSubmit} className="space-y-2 mb-4">
        <input
          type="file"
          accept=".fasta,.fastq"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
        <select value={format} onChange={(e) => setFormat(e.target.value)} className="border p-1">
          <option value="fasta">FASTA</option>
          <option value="fastq">FASTQ</option>
        </select>
        <button type="submit" className="bg-blue-500 text-white px-2 py-1">Submit</button>
      </form>
      {jobs && jobs.length > 0 && (
        <table className="table-auto border-collapse text-sm">
          <thead>
            <tr>
              <th className="border px-2">ID</th>
              <th className="border px-2">Status</th>
              <th className="border px-2">Format</th>
              <th className="border px-2">Created</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((j: SequenceJob) => (
              <tr key={j.id}>
                <td className="border px-2">{j.id.slice(0, 8)}</td>
                <td className="border px-2">{j.status}</td>
                <td className="border px-2">{j.format}</td>
                <td className="border px-2">{new Date(j.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
