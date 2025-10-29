'use client'

// purpose: DNA viewer route bridging backend payloads with UI renderers
// status: experimental

import { useMemo, useState } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'

import { Button, Input, LoadingState, EmptyState } from '../../components/ui'
import { useDNAViewer } from '../../hooks/useDNAViewer'
import { DNAViewerSummary } from '../components/DNAViewerSummary'

interface DNAViewerPageProps {
  params: { assetId: string }
}

const DNAViewerPage = ({ params }: DNAViewerPageProps) => {
  const searchParams = useSearchParams()
  const router = useRouter()
  const initialCompare = searchParams.get('compare')
  const [compareVersion, setCompareVersion] = useState<string | null>(initialCompare)

  const { data, isLoading, error, refetch, isFetching } = useDNAViewer(params.assetId, compareVersion)

  const handleCompareSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    const formData = new FormData(event.currentTarget as HTMLFormElement)
    const next = formData.get('compareVersion')?.toString().trim() || null
    setCompareVersion(next)
    const query = new URLSearchParams(searchParams.toString())
    if (next) {
      query.set('compare', next)
    } else {
      query.delete('compare')
    }
    router.replace(`/dna-viewer/${params.assetId}?${query.toString()}`)
  }

  const annotations = useMemo(() => data?.tracks.find((track) => track.name === 'Annotations'), [data])

  if (isLoading) {
    return (
      <div className="container mx-auto px-6 py-10">
        <LoadingState title="Loading DNA viewer" description="Fetching asset annotations and guardrail telemetry" />
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="container mx-auto px-6 py-10">
        <EmptyState
          title="DNA asset unavailable"
          description="The asset could not be loaded or you do not have access permissions."
        />
      </div>
    )
  }

  return (
    <div className="container mx-auto space-y-8 px-6 py-10">
      <form
        onSubmit={handleCompareSubmit}
        className="flex flex-wrap items-end gap-4 rounded border border-slate-200 bg-white p-4 shadow-sm"
      >
        <div className="min-w-[240px] flex-1">
          <label htmlFor="compareVersion" className="block text-sm font-semibold text-slate-700">
            Compare version ID
          </label>
          <Input
            id="compareVersion"
            name="compareVersion"
            placeholder="UUID of version to diff against latest"
            defaultValue={compareVersion ?? ''}
          />
        </div>
        <div className="flex items-center gap-2">
          <Button type="submit" variant="primary" disabled={isFetching}>
            Apply comparison
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              setCompareVersion(null)
              router.replace(`/dna-viewer/${params.assetId}`)
              refetch()
            }}
            disabled={isFetching || !compareVersion}
          >
            Clear
          </Button>
        </div>
      </form>

      <DNAViewerSummary payload={data} />

      {annotations && annotations.features.length === 0 && (
        <div className="rounded border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
          No annotations were detected for this asset. Upload enriched files or add annotations to unlock viewer overlays.
        </div>
      )}
    </div>
  )
}

export default DNAViewerPage
