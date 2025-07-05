'use client'
import { useState } from 'react'
import DynamicForm from '../components/DynamicForm'
import {
  useNotebookEntries,
  useCreateEntry,
  useUpdateEntry,
  useDeleteEntry,
} from '../hooks/useNotebook'
import type { NotebookEntry } from '../types'

export default function NotebookPage() {
  const { data: entries } = useNotebookEntries()
  const create = useCreateEntry()
  const update = useUpdateEntry()
  const remove = useDeleteEntry()
  const [editing, setEditing] = useState<NotebookEntry | null>(null)

  const fields = [
    {
      id: 'title',
      entity_type: 'notebook',
      field_key: 'title',
      field_label: 'Title',
      field_type: 'text',
      is_required: true,
    },
    {
      id: 'content',
      entity_type: 'notebook',
      field_key: 'content',
      field_label: 'Content',
      field_type: 'text',
      is_required: true,
    },
  ] as any

  const handleSubmit = (data: any) => {
    if (editing) {
      update.mutate({ id: editing.id, data })
      setEditing(null)
    } else {
      create.mutate(data)
    }
  }

  return (
    <div>
      <h1 className="text-xl mb-4">Lab Notebook</h1>
      <DynamicForm
        fields={fields}
        onSubmit={handleSubmit}
        defaultValues={editing ? { title: editing.title, content: editing.content } : {}}
      />
      {editing && (
        <button className="text-sm text-gray-600 mt-2" onClick={() => setEditing(null)}>
          Cancel Edit
        </button>
      )}
      <h2 className="text-lg mt-6 mb-2">Entries</h2>
      <ul className="space-y-2">
        {entries?.map((e) => (
          <li key={e.id} className="border p-2 space-y-1">
            <div className="flex justify-between items-center">
              <span className="font-semibold">{e.title}</span>
              <div className="space-x-2 text-sm">
                <button className="text-blue-600" onClick={() => setEditing(e)}>
                  Edit
                </button>
                <button className="text-red-600" onClick={() => remove.mutate(e.id)}>
                  Delete
                </button>
              </div>
            </div>
            <p className="text-sm whitespace-pre-wrap">{e.content}</p>
          </li>
        ))}
      </ul>
    </div>
  )
}
