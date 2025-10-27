'use client'

import React, { FormEvent, useMemo, useState } from 'react'
import type { BaselineLifecycleLabel } from '../../../types'

interface BaselineSubmissionFormProps {
  executionId: string
  templateName?: string | null
  onSubmit: (payload: {
    name: string
    description?: string | null
    reviewerIds: string[]
    labels: BaselineLifecycleLabel[]
  }) => void
  submitting?: boolean
  disabled?: boolean
  errorMessage?: string | null
}

// purpose: capture baseline submission metadata from experiment console scientists
// inputs: execution context identifiers, submission handler callbacks
// outputs: sanitized payload forwarded to mutation hooks for persistence
// status: pilot
export default function BaselineSubmissionForm({
  executionId,
  templateName,
  onSubmit,
  submitting = false,
  disabled = false,
  errorMessage = null,
}: BaselineSubmissionFormProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [reviewerInput, setReviewerInput] = useState('')
  const [labels, setLabels] = useState<Array<{ key: string; value: string }>>([
    { key: 'environment', value: '' },
  ])

  const reviewerSuggestions = useMemo(() => {
    return reviewerInput
      .split(',')
      .map((token) => token.trim())
      .filter(Boolean)
  }, [reviewerInput])

  const addLabelRow = () => {
    setLabels((prev) => [...prev, { key: '', value: '' }])
  }

  const updateLabel = (index: number, key: 'key' | 'value', value: string) => {
    setLabels((prev) => {
      const next = [...prev]
      next[index] = { ...next[index], [key]: value }
      return next
    })
  }

  const removeLabel = (index: number) => {
    setLabels((prev) => prev.filter((_, idx) => idx !== index))
  }

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (!name.trim()) {
      return
    }
    const parsedLabels: BaselineLifecycleLabel[] = labels
      .map((entry) => ({ key: entry.key.trim(), value: entry.value.trim() }))
      .filter((entry) => entry.key && entry.value)
    onSubmit({
      name: name.trim(),
      description: description.trim() ? description.trim() : null,
      reviewerIds: reviewerSuggestions,
      labels: parsedLabels,
    })
    setName('')
    setDescription('')
    setReviewerInput('')
    setLabels([{ key: 'environment', value: '' }])
  }

  return (
    <section
      className="border border-neutral-200 rounded-lg bg-white shadow-sm p-6 space-y-5"
      aria-labelledby={`baseline-submission-${executionId}`}
    >
      <header className="space-y-1">
        <p className="text-xs uppercase tracking-wide text-neutral-500" id={`baseline-submission-${executionId}`}>
          Submit baseline
        </p>
        <h2 className="text-xl font-semibold text-neutral-900">Baseline proposal</h2>
        <p className="text-sm text-neutral-600">
          Anchor ladder adjustments to <span className="font-medium">{templateName ?? 'this template'}</span>. Provide reviewers and
          metadata to route approvals automatically.
        </p>
      </header>

      {errorMessage && (
        <div className="border border-rose-200 bg-rose-50 text-rose-600 text-sm rounded-md p-3" role="alert">
          {errorMessage}
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid md:grid-cols-2 gap-4">
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-neutral-700">Baseline Name</span>
            <input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="E.g. Biosafety Ladder v3"
              className="rounded-md border border-neutral-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
              disabled={disabled}
              required
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium text-neutral-700">Reviewer Emails or IDs</span>
            <input
              type="text"
              value={reviewerInput}
              onChange={(event) => setReviewerInput(event.target.value)}
              placeholder="Comma separated identifiers"
              className="rounded-md border border-neutral-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
              disabled={disabled}
            />
            <span className="text-xs text-neutral-500">Separate entries with commas. Workspace enforces assignments server-side.</span>
          </label>
        </div>

        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium text-neutral-700">Context</span>
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Summarize the baseline adjustments and rationale"
            className="rounded-md border border-neutral-300 px-3 py-2 text-sm min-h-[120px] focus:outline-none focus:ring-2 focus:ring-primary-400"
            disabled={disabled}
          />
        </label>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-neutral-700">Lifecycle Labels</span>
            <button
              type="button"
              onClick={addLabelRow}
              className="text-xs font-semibold text-primary-600 hover:text-primary-700"
              disabled={disabled}
            >
              Add label
            </button>
          </div>
          <div className="space-y-2">
            {labels.map((entry, index) => (
              <div key={`label-${index}`} className="grid md:grid-cols-[1fr_1fr_auto] gap-2 items-start">
                <input
                  type="text"
                  value={entry.key}
                  onChange={(event) => updateLabel(index, 'key', event.target.value)}
                  placeholder="Key"
                  className="rounded-md border border-neutral-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
                  disabled={disabled}
                />
                <input
                  type="text"
                  value={entry.value}
                  onChange={(event) => updateLabel(index, 'value', event.target.value)}
                  placeholder="Value"
                  className="rounded-md border border-neutral-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
                  disabled={disabled}
                />
                <button
                  type="button"
                  onClick={() => removeLabel(index)}
                  className="text-xs font-medium text-neutral-500 hover:text-rose-600"
                  disabled={disabled || labels.length === 1}
                >
                  Remove
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-end gap-3">
          <span className="text-xs text-neutral-500">Execution {executionId}</span>
          <button
            type="submit"
            disabled={disabled || submitting}
            className="inline-flex items-center gap-2 rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-primary-700 transition disabled:opacity-60"
            data-testid="baseline-submit-button"
          >
            {submitting ? 'Submitting…' : 'Submit baseline'}
          </button>
        </div>
      </form>
    </section>
  )
}
