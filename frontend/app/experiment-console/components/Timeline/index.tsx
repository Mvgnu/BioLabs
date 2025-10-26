'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import type { ExecutionEvent } from '../../../types'
import { cn } from '../../../utils/cn'

const ITEM_HEIGHT = 108
const OVERSCAN = 4

export interface TimelineProps {
  events: ExecutionEvent[]
  isLoading?: boolean
  isFetchingMore?: boolean
  hasMore?: boolean
  activeTypes?: string[]
  onTypesChange?: (types: string[]) => void
  onLoadMore?: () => void
  annotations?: Record<string, string>
  onAnnotate?: (eventId: string, note: string) => void
}

const formatTimestamp = (value: string) => {
  try {
    return new Intl.DateTimeFormat('en', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(new Date(value))
  } catch (error) {
    return value
  }
}

const formatEventType = (value: string) => value.replace(/[_:.]/g, ' ')

const summarizePayload = (payload: Record<string, any>) => {
  const entries = Object.entries(payload ?? {})
  if (entries.length === 0) return '—'
  return entries
    .slice(0, 4)
    .map(([key, raw]) => {
      if (raw === null || raw === undefined) return `${key}: —`
      if (typeof raw === 'object') {
        try {
          return `${key}: ${JSON.stringify(raw)}`
        } catch (error) {
          return `${key}: [object]`
        }
      }
      return `${key}: ${raw}`
    })
    .join(' • ')
}

// purpose: virtualised execution timeline presentation for experiment console
// inputs: events array, loading flags, filter callbacks, annotation ledger
// outputs: scrollable UI with lazy loading, filter toggles, inline annotations
// status: pilot
const Timeline = ({
  events,
  isLoading = false,
  isFetchingMore = false,
  hasMore = false,
  activeTypes,
  onTypesChange,
  onLoadMore,
  annotations = {},
  onAnnotate,
}: TimelineProps) => {
  const scrollRef = useRef<HTMLDivElement | null>(null)
  const [scrollTop, setScrollTop] = useState(0)
  const [containerHeight, setContainerHeight] = useState(480)
  const [draftNotes, setDraftNotes] = useState<Record<string, string>>({})
  const [editingId, setEditingId] = useState<string | null>(null)
  const loadRef = useRef(false)

  const activeKey = activeTypes?.slice().sort().join('|') ?? ''

  useEffect(() => {
    const node = scrollRef.current
    if (!node) return
    if (typeof ResizeObserver === 'undefined') {
      setContainerHeight(node.clientHeight || 480)
      return
    }
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry) {
        setContainerHeight(entry.contentRect.height)
      }
    })
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const node = scrollRef.current
    if (!node) return
    const handleScroll = () => {
      const nextTop = node.scrollTop
      setScrollTop(nextTop)
      if (
        hasMore &&
        onLoadMore &&
        !loadRef.current &&
        !isFetchingMore &&
        nextTop + node.clientHeight >= node.scrollHeight - ITEM_HEIGHT * 2
      ) {
        loadRef.current = true
        onLoadMore()
      }
    }
    node.addEventListener('scroll', handleScroll)
    return () => node.removeEventListener('scroll', handleScroll)
  }, [hasMore, onLoadMore, isFetchingMore])

  useEffect(() => {
    if (!isFetchingMore) {
      loadRef.current = false
    }
  }, [isFetchingMore])

  useEffect(() => {
    const node = scrollRef.current
    if (node) {
      node.scrollTop = 0
      setScrollTop(0)
    }
  }, [activeKey])

  const totalHeight = Math.max(events.length * ITEM_HEIGHT, containerHeight)
  const visibleCount = Math.ceil(containerHeight / ITEM_HEIGHT) + OVERSCAN * 2
  const startIndex = Math.max(0, Math.floor(scrollTop / ITEM_HEIGHT) - OVERSCAN)
  const endIndex = Math.min(events.length, startIndex + visibleCount)
  const slice = events.slice(startIndex, endIndex)
  const offsetY = startIndex * ITEM_HEIGHT

  const availableTypes = useMemo(() => {
    const unique = new Set(events.map((event) => event.event_type))
    return Array.from(unique).sort()
  }, [events])

  const handleToggleType = (type: string) => {
    if (!onTypesChange) return
    const next = new Set(activeTypes ?? [])
    if (next.has(type)) {
      next.delete(type)
    } else {
      next.add(type)
    }
    onTypesChange(Array.from(next))
  }

  const handleAnnotate = (eventId: string) => {
    const note = draftNotes[eventId] ?? ''
    if (onAnnotate) {
      onAnnotate(eventId, note)
    }
    setEditingId(null)
  }

  const editingValue = editingId ? draftNotes[editingId] ?? annotations[editingId] ?? '' : ''

  return (
    <section className="border border-neutral-200 rounded-lg bg-white shadow-sm">
      <header className="flex items-center justify-between gap-4 border-b border-neutral-100 px-4 py-3">
        <div>
          <h2 className="text-lg font-semibold text-neutral-900">Execution Timeline</h2>
          <p className="text-sm text-neutral-500">
            Streamed orchestration events with inline annotations.
          </p>
        </div>
        {availableTypes.length > 0 && (
          <div className="flex flex-wrap gap-2 justify-end">
            {availableTypes.map((type) => {
              const isActive =
                !activeTypes || activeTypes.length === 0 || activeTypes.includes(type)
              return (
                <button
                  key={type}
                  type="button"
                  onClick={() => handleToggleType(type)}
                  className={cn(
                    'text-xs px-3 py-1 rounded-full border transition-colors',
                    isActive
                      ? 'border-blue-200 bg-blue-50 text-blue-700'
                      : 'border-neutral-200 text-neutral-600 hover:bg-neutral-50',
                  )}
                >
                  {formatEventType(type)}
                </button>
              )
            })}
            {onTypesChange && activeTypes && activeTypes.length > 0 && (
              <button
                type="button"
                onClick={() => onTypesChange([])}
                className="text-xs px-3 py-1 rounded-full border border-neutral-200 text-neutral-600 hover:bg-neutral-50"
              >
                Show all
              </button>
            )}
          </div>
        )}
      </header>
      <div
        ref={scrollRef}
        className="relative max-h-[32rem] min-h-[20rem] overflow-y-auto px-4"
      >
        {events.length === 0 && !isLoading ? (
          <div className="flex h-full items-center justify-center text-sm text-neutral-500">
            No timeline events captured yet.
          </div>
        ) : (
          <div style={{ height: totalHeight }}>
            <div
              className="absolute left-8 top-0 w-px bg-neutral-200"
              style={{ height: totalHeight }}
            />
            <div
              style={{ transform: `translateY(${offsetY}px)` }}
              className="relative"
            >
              {slice.map((event) => {
                const annotation = annotations[event.id]
                const isEditing = editingId === event.id
                return (
                  <article
                    key={event.id}
                    className="relative flex gap-4 py-4 pl-6"
                    style={{ height: ITEM_HEIGHT }}
                  >
                    <span className="absolute left-7 top-4 h-3 w-3 rounded-full bg-blue-500" />
                    <div className="flex-1 space-y-1">
                      <header className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex flex-col">
                          <span className="text-sm font-semibold text-neutral-800">
                            {formatEventType(event.event_type)}
                          </span>
                          <span className="text-xs text-neutral-500">
                            {formatTimestamp(event.created_at)}
                          </span>
                        </div>
                        <span className="text-xs rounded-full bg-neutral-100 px-2 py-1 text-neutral-600">
                          #{event.sequence}
                        </span>
                      </header>
                      <p className="text-sm text-neutral-600">
                        {summarizePayload(event.payload)}
                      </p>
                      {event.actor && (
                        <p className="text-xs text-neutral-500">
                          Actor: {event.actor.full_name ?? event.actor.email}
                        </p>
                      )}
                      {annotation && !isEditing && (
                        <p className="text-xs text-blue-600">Annotation: {annotation}</p>
                      )}
                      {isEditing && (
                        <div className="space-y-2">
                          <textarea
                            value={editingValue}
                            onChange={(event) =>
                              setDraftNotes((prev) => ({
                                ...prev,
                                [event.id]: event.target.value,
                              }))
                            }
                            className="w-full rounded-md border border-neutral-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                            rows={3}
                            placeholder="Add contextual notes for this event"
                          />
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              onClick={() => handleAnnotate(event.id)}
                              className="rounded-md bg-blue-600 px-3 py-1 text-xs font-semibold text-white hover:bg-blue-700"
                            >
                              Save annotation
                            </button>
                            <button
                              type="button"
                              onClick={() => setEditingId(null)}
                              className="text-xs text-neutral-500 hover:text-neutral-700"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      )}
                      {!isEditing && (
                        <button
                          type="button"
                          onClick={() => {
                            setEditingId(event.id)
                            setDraftNotes((prev) => ({
                              ...prev,
                              [event.id]: prev[event.id] ?? annotations[event.id] ?? '',
                            }))
                          }}
                          className="text-xs font-medium text-blue-600 hover:text-blue-700"
                        >
                          {annotation ? 'Edit annotation' : 'Add annotation'}
                        </button>
                      )}
                    </div>
                  </article>
                )
              })}
            </div>
          </div>
        )}
        {(isLoading || isFetchingMore) && (
          <div className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-center pb-4">
            <span className="rounded-full bg-white/80 px-3 py-1 text-xs text-neutral-500">
              {isLoading ? 'Loading timeline…' : 'Fetching additional events…'}
            </span>
          </div>
        )}
      </div>
    </section>
  )
}

export default Timeline
