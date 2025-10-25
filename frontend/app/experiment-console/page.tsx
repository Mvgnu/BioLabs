'use client'

import { FormEvent, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { useProtocolTemplates } from '../hooks/useProtocols'
import { useCreateExperimentSession } from '../hooks/useExperimentConsole'

const parseCsv = (value: string) =>
  value
    .split(',')
    .map((token) => token.trim())
    .filter(Boolean)

export default function ExperimentConsoleIndex() {
  const router = useRouter()
  const { data: templates = [] } = useProtocolTemplates()
  const createSession = useCreateExperimentSession()

  const [selectedTemplate, setSelectedTemplate] = useState<string>('')
  const [sessionTitle, setSessionTitle] = useState('')
  const [inventoryInput, setInventoryInput] = useState('')
  const [bookingInput, setBookingInput] = useState('')

  const templateOptions = useMemo(
    () => templates.map((tpl) => ({ value: tpl.id, label: `${tpl.name} · v${tpl.version}` })),
    [templates],
  )

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!selectedTemplate) return
    createSession.mutate(
      {
        template_id: selectedTemplate,
        title: sessionTitle || undefined,
        inventory_item_ids: parseCsv(inventoryInput),
        booking_ids: parseCsv(bookingInput),
      },
      {
        onSuccess: (data) => {
          router.push(`/experiment-console/${data.execution.id}`)
        },
      },
    )
  }

  return (
    <div className="p-8 space-y-8">
      <header className="space-y-3">
        <h1 className="text-3xl font-semibold">Experiment Execution Console</h1>
        <p className="text-neutral-600 max-w-3xl">
          Launch a unified execution workspace that blends protocol steps, inventory pulls, instrumentation bookings,
          and live notebook logging. After creating a session, you will be redirected to the immersive console view.
        </p>
      </header>

      <section className="border border-neutral-200 rounded-xl bg-white shadow-sm p-6">
        <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="md:col-span-2">
            <label className="block text-sm font-medium text-neutral-700">Protocol Template</label>
            <select
              value={selectedTemplate}
              onChange={(event) => setSelectedTemplate(event.target.value)}
              className="mt-1 block w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-200"
              required
            >
              <option value="" disabled>
                Select a protocol template
              </option>
              {templateOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-neutral-700">Session Title</label>
            <input
              type="text"
              value={sessionTitle}
              onChange={(event) => setSessionTitle(event.target.value)}
              placeholder="Optional custom title"
              className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-200"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-neutral-700">Inventory Item IDs</label>
            <input
              type="text"
              value={inventoryInput}
              onChange={(event) => setInventoryInput(event.target.value)}
              placeholder="Comma-separated identifiers"
              className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-200"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-neutral-700">Booking IDs</label>
            <input
              type="text"
              value={bookingInput}
              onChange={(event) => setBookingInput(event.target.value)}
              placeholder="Comma-separated identifiers"
              className="mt-1 block w-full rounded-md border border-neutral-300 px-3 py-2 text-sm focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-200"
            />
          </div>

          <div className="md:col-span-2 flex items-center justify-between">
            <p className="text-sm text-neutral-500">
              Need to prepare resources first?{' '}
              <Link href="/protocols" className="text-primary-600 hover:underline">
                Manage templates
              </Link>{' '}
              or{' '}
              <Link href="/inventory" className="text-primary-600 hover:underline">
                curate inventory
              </Link>
              .
            </p>
            <button
              type="submit"
              disabled={createSession.isPending}
              className="inline-flex items-center gap-2 rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-700 transition-colors disabled:opacity-60"
            >
              {createSession.isPending ? 'Starting…' : 'Launch Execution Console'}
            </button>
          </div>
        </form>
      </section>

      <section className="space-y-3">
        <h2 className="text-xl font-semibold">Recent Protocols</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {templates.map((tpl) => (
            <article key={tpl.id} className="border border-neutral-200 rounded-lg bg-white shadow-sm p-4 space-y-2">
              <header>
                <h3 className="text-lg font-medium">{tpl.name}</h3>
                <p className="text-xs text-neutral-500">Version {tpl.version}</p>
              </header>
              <p className="text-sm text-neutral-600 whitespace-pre-wrap line-clamp-3">
                {tpl.content}
              </p>
              <button
                onClick={() => {
                  setSelectedTemplate(tpl.id)
                  setSessionTitle(`${tpl.name} Execution`)
                }}
                className="text-sm text-primary-600 hover:text-primary-700 hover:underline"
              >
                Prefill launch form
              </button>
            </article>
          ))}
        </div>
      </section>
    </div>
  )
}
