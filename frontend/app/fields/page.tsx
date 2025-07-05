'use client'
import { useState } from 'react'
import { useFieldDefinitions, useCreateField, useDeleteField } from '../hooks/useFields'
import DynamicForm from '../components/DynamicForm'

export default function FieldDefinitionsPage() {
  const [entity, setEntity] = useState('sample')
  const { data: fields } = useFieldDefinitions(entity)
  const createField = useCreateField()
  const deleteField = useDeleteField()

  const handleCreate = (data: any) => {
    createField.mutate({ ...data, entity_type: entity })
  }

  return (
    <div>
      <h1 className="text-xl mb-4">Field Definitions</h1>
      <div className="mb-4 flex gap-2 items-center">
        <label>Entity</label>
        <input
          className="border p-1"
          value={entity}
          onChange={(e) => setEntity(e.target.value)}
        />
      </div>
      <DynamicForm
        fields={[
          { id: 'field_key', entity_type: entity, field_key: 'field_key', field_label: 'Key', field_type: 'text', is_required: true },
          { id: 'field_label', entity_type: entity, field_key: 'field_label', field_label: 'Label', field_type: 'text', is_required: true },
          { id: 'field_type', entity_type: entity, field_key: 'field_type', field_label: 'Type', field_type: 'select', is_required: true, options: [
            { label: 'text', value: 'text' },
            { label: 'number', value: 'number' },
            { label: 'date', value: 'date' },
          ] }
        ]}
        onSubmit={handleCreate}
      />
      <h2 className="text-lg mt-6 mb-2">Fields for {entity}</h2>
      <ul className="space-y-2">
        {fields?.map((f) => (
          <li key={f.id} className="border p-2 flex justify-between">
            <span>{f.field_label} ({f.field_key})</span>
            <button onClick={() => deleteField.mutate({ id: f.id, entity })}>Delete</button>
          </li>
        ))}
      </ul>
    </div>
  )
}
