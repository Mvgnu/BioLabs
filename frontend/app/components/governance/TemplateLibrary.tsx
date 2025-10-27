'use client'
import React from 'react'
import type { GovernanceTemplate } from '../../types'
import { Button, Card, CardBody, LoadingState } from '../ui'

interface TemplateLibraryProps {
  templates: GovernanceTemplate[]
  isLoading?: boolean
  onSelect: (templateId: string | null) => void
  onCreateNew: () => void
  onFork: (template: GovernanceTemplate) => void
  selectedTemplateId: string | null
}

// purpose: render governance template catalog with selection affordances
// inputs: template collection and selection callbacks
// outputs: interactive grid list for admin workspace
// status: experimental
export default function TemplateLibrary({
  templates,
  isLoading,
  onSelect,
  onCreateNew,
  onFork,
  selectedTemplateId,
}: TemplateLibraryProps) {
  if (isLoading) {
    return (
      <Card>
        <CardBody>
          <LoadingState message="Loading governance templates" />
        </CardBody>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-neutral-800">Workflow Templates</h2>
          <p className="text-sm text-neutral-500">
            Manage narrative ladders, status transitions, and SLA policy.
          </p>
        </div>
        <Button onClick={onCreateNew}>New template</Button>
      </div>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {templates.map((template) => {
          const isSelected = selectedTemplateId === template.id
          return (
            <Card
              variant="outlined"
              key={template.id}
              className={` ${
                isSelected
                  ? 'border-primary-500 shadow-lg'
                  : 'border-neutral-200 shadow-sm'
              } transition`}
            >
              <CardBody className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-base font-semibold text-neutral-800">
                      {template.name}
                    </h3>
                    <p className="text-xs uppercase tracking-wide text-neutral-500">
                      {template.template_key} · v{template.version}
                    </p>
                  </div>
                  <span
                    className={`text-xs font-medium px-2 py-1 rounded-full ${
                      template.status === 'published'
                        ? 'bg-emerald-100 text-emerald-700'
                        : 'bg-amber-100 text-amber-700'
                    }`}
                  >
                    {template.status}
                  </span>
                </div>
                <p className="text-sm text-neutral-600 line-clamp-2">
                  {template.description || 'No description provided.'}
                </p>
                <div className="flex items-center justify-between text-xs text-neutral-500">
                  <span>Stages: {template.stage_blueprint.length}</span>
                  <span>Roles: {template.permitted_roles.join(', ') || '—'}</span>
                </div>
                <div className="flex justify-between gap-2">
                  <Button
                    variant={isSelected ? 'primary' : 'secondary'}
                    className="flex-1"
                    onClick={() => onSelect(template.id)}
                  >
                    {isSelected ? 'Selected' : 'Open'}
                  </Button>
                  <Button variant="ghost" onClick={() => onFork(template)}>
                    Fork
                  </Button>
                </div>
              </CardBody>
            </Card>
          )
        })}
        {templates.length === 0 && (
          <Card className="sm:col-span-2 xl:col-span-3">
            <CardBody className="text-sm text-neutral-500">
              No workflow templates yet. Create one to get started.
            </CardBody>
          </Card>
        )}
      </div>
    </div>
  )
}
