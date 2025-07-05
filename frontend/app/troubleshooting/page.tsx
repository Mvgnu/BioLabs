'use client'
import { useState } from 'react'
import {
  useArticles,
  useCreateArticle,
  useUpdateArticle,
  useMarkSuccess,
} from '../hooks/useTroubleshooting'
import DynamicForm from '../components/DynamicForm'
import type { TroubleshootingArticle } from '../types'

export default function TroubleshootingPage() {
  const [category, setCategory] = useState('')
  const { data: articles } = useArticles(category || undefined)
  const create = useCreateArticle()
  const update = useUpdateArticle()
  const mark = useMarkSuccess()
  const [editing, setEditing] = useState<TroubleshootingArticle | null>(null)

  const fields = [
    {
      id: 'title',
      entity_type: 'troubleshooting',
      field_key: 'title',
      field_label: 'Title',
      field_type: 'text',
      is_required: true,
    },
    {
      id: 'category',
      entity_type: 'troubleshooting',
      field_key: 'category',
      field_label: 'Category',
      field_type: 'text',
      is_required: true,
    },
    {
      id: 'content',
      entity_type: 'troubleshooting',
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
      <h1 className="text-xl mb-4">Troubleshooting</h1>
      <div className="mb-4 flex gap-2 items-center">
        <label>Category</label>
        <input
          className="border p-1"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        />
      </div>
      <DynamicForm
        fields={fields}
        onSubmit={handleSubmit}
        defaultValues={
          editing
            ? { title: editing.title, category: editing.category, content: editing.content }
            : {}
        }
      />
      {editing && (
        <button className="text-sm text-gray-600 mt-2" onClick={() => setEditing(null)}>
          Cancel Edit
        </button>
      )}
      <h2 className="text-lg mt-6 mb-2">Articles</h2>
      <ul className="space-y-2">
        {articles?.map((a) => (
          <li key={a.id} className="border p-2 space-y-1">
            <div className="flex justify-between items-center">
              <span className="font-semibold">
                {a.title} <span className="text-xs text-gray-600">({a.category})</span>
              </span>
              <div className="space-x-2 text-sm">
                <button className="text-blue-600" onClick={() => setEditing(a)}>
                  Edit
                </button>
                <button className="text-green-600" onClick={() => mark.mutate(a.id)}>
                  Mark Success ({a.success_count})
                </button>
              </div>
            </div>
            <p className="text-sm">{a.content}</p>
          </li>
        ))}
      </ul>
    </div>
  )
}
