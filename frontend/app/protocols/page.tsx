'use client'
import { useState } from 'react'
import Link from 'next/link'
import DynamicForm from '../components/DynamicForm'
import {
  useProtocolTemplates,
  useCreateTemplate,
  useUpdateTemplate,
  useDeleteTemplate,
  useProtocolExecutions,
  useCreateExecution,
  useUpdateExecution,
} from '../hooks/useProtocols'

export default function ProtocolsPage() {
  const { data: templates } = useProtocolTemplates()
  const { data: executions } = useProtocolExecutions()
  const createTemplate = useCreateTemplate()
  const updateTemplate = useUpdateTemplate()
  const deleteTemplate = useDeleteTemplate()
  const createExecution = useCreateExecution()
  const updateExecution = useUpdateExecution()
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<string | null>(null)

  const fields = [
    {
      id: 'name',
      entity_type: 'protocol',
      field_key: 'name',
      field_label: 'Name',
      field_type: 'text',
      is_required: true,
    },
    {
      id: 'content',
      entity_type: 'protocol',
      field_key: 'content',
      field_label: 'Content',
      field_type: 'text',
      is_required: true,
    },
  ] as any

  const submit = (data: any) => {
    if (editing) {
      updateTemplate.mutate({ id: editing, data })
      setEditing(null)
    } else {
      createTemplate.mutate(data)
    }
    setShowForm(false)
  }

  return (
    <div>
      <h1 className="text-xl mb-4">Protocols</h1>
      <Link href="/protocols/diff" className="text-blue-600 underline">
        Diff Viewer
      </Link>
      {showForm ? (
        <div className="mb-4">
          <DynamicForm fields={fields} onSubmit={submit} />
          <button
            className="text-sm text-gray-600 mt-2"
            onClick={() => setShowForm(false)}
          >
            Cancel
          </button>
        </div>
      ) : (
        <button className="mb-4 text-blue-600" onClick={() => setShowForm(true)}>
          New Template
        </button>
      )}

      <h2 className="text-lg mb-2">Templates</h2>
      <ul className="space-y-2">
        {templates?.map((t) => (
          <li key={t.id} className="border p-2 space-y-1">
            <div className="flex justify-between items-center">
              <span className="font-semibold">
                {t.name} <span className="text-xs text-gray-600">v{t.version}</span>
              </span>
              <div className="space-x-2">
                <button
                  className="text-blue-600 text-sm"
                  onClick={() => createExecution.mutate({ template_id: t.id })}
                >
                  Run
                </button>
                <button
                  className="text-sm text-gray-600"
                  onClick={() => setEditing(t.id)}
                >
                  Edit
                </button>
                <button
                  className="text-sm text-red-600"
                  onClick={() => deleteTemplate.mutate(t.id)}
                >
                  Delete
                </button>
              </div>
            </div>
            <pre className="text-sm whitespace-pre-wrap">{t.content}</pre>
            {editing === t.id && (
              <DynamicForm
                fields={fields}
                onSubmit={submit}
                defaultValues={{ name: t.name, content: t.content }}
              />
            )}
          </li>
        ))}
      </ul>

      <h2 className="text-lg mt-6 mb-2">Executions</h2>
      <ul className="space-y-2">
        {executions?.map((e) => (
          <li key={e.id} className="border p-2 flex justify-between items-center">
            <span>
              {e.template_id.slice(0, 8)}... - {e.status}
            </span>
            {e.status !== 'completed' && (
              <button
                className="text-blue-600 text-sm"
                onClick={() =>
                  updateExecution.mutate({
                    id: e.id,
                    data: { status: 'completed', result: { ok: true } },
                  })
                }
              >
                Mark Complete
              </button>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
