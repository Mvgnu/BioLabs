'use client'
import { useState } from 'react'
import {
  useCalendarEvents,
  useCreateEvent,
  useUpdateEvent,
  useDeleteEvent,
} from '../hooks/useCalendar'

export default function CalendarPage() {
  const { data: events } = useCalendarEvents()
  const createEvent = useCreateEvent()
  const updateEvent = useUpdateEvent()
  const deleteEvent = useDeleteEvent()

  const [title, setTitle] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')

  const submit = () => {
    if (!title || !start || !end) return
    createEvent.mutate({ title, start_time: start, end_time: end })
    setTitle('')
    setStart('')
    setEnd('')
  }

  return (
    <div>
      <h1 className="text-xl mb-4">Calendar</h1>
      <div className="space-x-2 mb-4">
        <input
          className="border p-1"
          placeholder="Title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
        <input
          type="datetime-local"
          className="border p-1"
          value={start}
          onChange={(e) => setStart(e.target.value)}
        />
        <input
          type="datetime-local"
          className="border p-1"
          value={end}
          onChange={(e) => setEnd(e.target.value)}
        />
        <button className="bg-blue-500 text-white px-2" onClick={submit}>
          Add
        </button>
      </div>
      <ul className="space-y-2">
        {events?.map((ev) => (
          <li key={ev.id} className="border p-2 flex justify-between">
            <span>
              {ev.title} - {new Date(ev.start_time).toLocaleString()} to{' '}
              {new Date(ev.end_time).toLocaleString()}
            </span>
            <div className="space-x-2 text-sm">
              <button
                className="text-blue-600"
                onClick={() =>
                  updateEvent.mutate({ id: ev.id, data: { title: ev.title + '!' } })
                }
              >
                Bump Title
              </button>
              <button
                className="text-red-600"
                onClick={() => deleteEvent.mutate(ev.id)}
              >
                Delete
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
