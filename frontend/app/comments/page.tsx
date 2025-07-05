'use client'
import { useState } from 'react'
import DynamicForm from '../components/DynamicForm'
import {
  useComments,
  useCreateComment,
  useUpdateComment,
  useDeleteComment,
} from '../hooks/useComments'
import type { Comment } from '../types'

export default function CommentsPage() {
  const { data: comments } = useComments()
  const create = useCreateComment()
  const update = useUpdateComment()
  const remove = useDeleteComment()
  const [editing, setEditing] = useState<Comment | null>(null)

  const fields = [
    {
      id: 'content',
      entity_type: 'comment',
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
      <h1 className="text-xl mb-4">Comments</h1>
      <DynamicForm fields={fields} onSubmit={handleSubmit} defaultValues={editing ? { content: editing.content } : {}} />
      {editing && (
        <button className="text-sm text-gray-600 mt-2" onClick={() => setEditing(null)}>
          Cancel Edit
        </button>
      )}
      <h2 className="text-lg mt-6 mb-2">All Comments</h2>
      <ul className="space-y-2">
        {comments?.map((c) => (
          <li key={c.id} className="border p-2 space-y-1">
            <div className="flex justify-between items-center">
              <span className="font-semibold">{c.content}</span>
              <div className="space-x-2 text-sm">
                <button className="text-blue-600" onClick={() => setEditing(c)}>
                  Edit
                </button>
                <button className="text-red-600" onClick={() => remove.mutate(c.id)}>
                  Delete
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
