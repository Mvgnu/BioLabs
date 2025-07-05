'use client'
import { useState } from 'react'
import DynamicForm from '../components/DynamicForm'
import {
  useKnowledge,
  useCreateArticle,
  useUpdateArticle,
  useDeleteArticle,
} from '../hooks/useKnowledge'
import type { KnowledgeArticle } from '../types'

export default function KnowledgePage() {
  const { data: articles } = useKnowledge()
  const create = useCreateArticle()
  const update = useUpdateArticle()
  const remove = useDeleteArticle()
  const [editing, setEditing] = useState<KnowledgeArticle | null>(null)

  const fields = [
    { id: 'title', entity_type: 'ka', field_key: 'title', field_label: 'Title', field_type: 'text', is_required: true },
    { id: 'content', entity_type: 'ka', field_key: 'content', field_label: 'Content', field_type: 'text', is_required: true },
    { id: 'tags', entity_type: 'ka', field_key: 'tags', field_label: 'Tags (comma separated)', field_type: 'text' },
  ] as any

  const handleSubmit = (data: any) => {
    if (data.tags) {
      data.tags = data.tags.split(',').map((t: string) => t.trim())
    }
    if (editing) {
      update.mutate({ id: editing.id, data })
      setEditing(null)
    } else {
      create.mutate(data)
    }
  }

  return (
    <div>
      <h1 className="text-xl mb-4">Knowledge Base</h1>
      <DynamicForm fields={fields} onSubmit={handleSubmit} defaultValues={editing ? editing : {}} />
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
              <span className="font-semibold">{a.title}</span>
              <div className="space-x-2 text-sm">
                <button className="text-blue-600" onClick={() => setEditing(a)}>Edit</button>
                <button className="text-red-600" onClick={() => remove.mutate(a.id)}>Delete</button>
              </div>
            </div>
            <p className="text-sm text-gray-700">{a.content}</p>
            {a.tags && <p className="text-xs text-gray-500">Tags: {a.tags.join(', ')}</p>}
          </li>
        ))}
      </ul>
    </div>
  )
}
