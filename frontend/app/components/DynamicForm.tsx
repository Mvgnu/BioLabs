'use client'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'
import type { FieldDefinition } from '../types'

export default function DynamicForm({
  fields,
  onSubmit,
  defaultValues = {},
}: {
  fields: FieldDefinition[]
  onSubmit: (data: any) => void
  defaultValues?: Record<string, any>
}) {
  const shape = fields.reduce((acc, field) => {
    let fieldSchema: any = z.string()
    if (field.field_type === 'number') fieldSchema = z.number()
    if (field.field_type === 'date') fieldSchema = z.coerce.date()

    const rules = field.validation || {}
    if (field.field_type === 'number') {
      if (rules.min !== undefined) fieldSchema = fieldSchema.min(rules.min)
      if (rules.max !== undefined) fieldSchema = fieldSchema.max(rules.max)
    } else if (field.field_type === 'text') {
      if (rules.minLength !== undefined)
        fieldSchema = fieldSchema.min(rules.minLength)
      if (rules.maxLength !== undefined)
        fieldSchema = fieldSchema.max(rules.maxLength)
      if (rules.pattern)
        fieldSchema = fieldSchema.regex(new RegExp(rules.pattern))
    }

    if (!field.is_required) fieldSchema = fieldSchema.optional()
    acc[field.field_key] = fieldSchema
    return acc
  }, {} as any)

  const schema = z.object(shape)

  const form = useForm({ resolver: zodResolver(schema), defaultValues })

  return (
    <form
      onSubmit={form.handleSubmit(onSubmit)}
      className="space-y-2 border p-4"
    >
      {fields.map((field) => (
        <div key={field.field_key} className="flex flex-col gap-1">
          <label className="text-sm">{field.field_label}</label>
          {field.field_type === 'text' && (
            <input
              className="border p-2"
              {...form.register(field.field_key)}
            />
          )}
          {field.field_type === 'number' && (
            <input
              type="number"
              className="border p-2"
              {...form.register(field.field_key, { valueAsNumber: true })}
            />
          )}
          {field.field_type === 'date' && (
            <input
              type="date"
              className="border p-2"
              {...form.register(field.field_key, { valueAsDate: true })}
            />
          )}
          {field.field_type === 'select' && (
            <select className="border p-2" {...form.register(field.field_key)}>
              {field.options?.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          )}
        </div>
      ))}
      <button className="bg-blue-500 text-white px-4 py-2" type="submit">
        Submit
      </button>
    </form>
  )
}
