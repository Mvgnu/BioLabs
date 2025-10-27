'use client'
import React, { useEffect, useMemo, useState } from 'react'
import type {
  GovernanceTemplate,
  GovernanceTemplateAssignment,
  GovernanceTemplateDraft,
} from '../../types'
import { Button, Card, CardBody, Input, Alert } from '../ui'
import LadderBuilder from './LadderBuilder'
import LadderSimulationWidget from './LadderSimulationWidget'

interface TemplateEditorProps {
  draft: GovernanceTemplateDraft
  template?: GovernanceTemplate | null
  onDraftChange:
    | ((draft: GovernanceTemplateDraft) => void)
    | ((updater: (current: GovernanceTemplateDraft) => GovernanceTemplateDraft) => void)
  onSaveDraft: () => Promise<void> | void
  onPublish: () => Promise<void> | void
  onCancel: () => void
  assignments: GovernanceTemplateAssignment[]
  onCreateAssignment: (target: {
    team_id?: string | null
    protocol_template_id?: string | null
    metadata?: Record<string, any>
  }) => void
  onDeleteAssignment: (assignmentId: string) => void
  isSaving?: boolean
  assignError?: string | null
}

// purpose: governance template authoring form with ladder builder integration
// inputs: draft state, persistence callbacks, assignment handlers
// outputs: fully composed editing surface for admin workflow
// status: experimental
export default function TemplateEditor({
  draft,
  template,
  onDraftChange,
  onSaveDraft,
  onPublish,
  onCancel,
  assignments,
  onCreateAssignment,
  onDeleteAssignment,
  isSaving,
  assignError,
}: TemplateEditorProps) {
  const [assignmentTarget, setAssignmentTarget] = useState({
    team_id: '',
    protocol_template_id: '',
  })

  const effectiveDefaultSla = draft.default_stage_sla_hours ?? 0

  const permittedRoleString = useMemo(() => draft.permitted_roles.join(', '), [draft.permitted_roles])

  useEffect(() => {
    if (template && !draft.forked_from_id) {
      if (typeof onDraftChange === 'function') {
        onDraftChange((current) => ({ ...current, forked_from_id: template.id }))
      }
    }
  }, [draft.forked_from_id, onDraftChange, template])

  const updateDraft = (partial: Partial<GovernanceTemplateDraft>) => {
    if (typeof onDraftChange === 'function') {
      onDraftChange((current) => ({
        ...current,
        ...partial,
        permitted_roles: partial.permitted_roles ?? current.permitted_roles,
        stage_blueprint: partial.stage_blueprint ?? current.stage_blueprint,
      }))
    }
  }

  const updatePermittedRoles = (value: string) => {
    const roles = value
      .split(',')
      .map((role) => role.trim())
      .filter(Boolean)
    updateDraft({ permitted_roles: roles })
  }

  const handleAssignmentSubmit = () => {
    if (!assignmentTarget.team_id && !assignmentTarget.protocol_template_id) {
      return
    }
    onCreateAssignment({
      team_id: assignmentTarget.team_id || undefined,
      protocol_template_id: assignmentTarget.protocol_template_id || undefined,
    })
    setAssignmentTarget({ team_id: '', protocol_template_id: '' })
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardBody className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-neutral-800">
                {template ? template.name : 'New workflow template'}
              </h2>
              <p className="text-sm text-neutral-500">
                {template
                  ? 'Fork or iterate on the selected workflow template.'
                  : 'Define governance metadata before publishing the workflow.'}
              </p>
            </div>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={onCancel}>
                Close
              </Button>
              <Button variant="secondary" onClick={() => onSaveDraft()} disabled={isSaving}>
                {isSaving ? 'Saving…' : 'Save draft'}
              </Button>
              <Button onClick={() => onPublish()} disabled={isSaving}>
                {isSaving ? 'Publishing…' : 'Publish'}
              </Button>
            </div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              label="Template key"
              value={draft.template_key}
              onChange={(event) => updateDraft({ template_key: event.target.value })}
              disabled={Boolean(template)}
            />
            <Input
              label="Template name"
              value={draft.name}
              onChange={(event) => updateDraft({ name: event.target.value })}
            />
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-2">
                Description
              </label>
              <textarea
                className="w-full rounded-md border border-neutral-300 px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                rows={4}
                value={draft.description ?? ''}
                onChange={(event) => updateDraft({ description: event.target.value })}
              />
            </div>
            <Input
              label="Default stage SLA (hours)"
              type="number"
              value={draft.default_stage_sla_hours ?? ''}
              onChange={(event) =>
                updateDraft({
                  default_stage_sla_hours: event.target.value
                    ? Number(event.target.value)
                    : undefined,
                })
              }
            />
            <Input
              label="Permitted roles (comma separated)"
              value={permittedRoleString}
              onChange={(event) => updatePermittedRoles(event.target.value)}
              placeholder="scientist, quality, compliance"
            />
          </div>
          <div className="space-y-3">
            <h3 className="text-md font-semibold text-neutral-800">Approval ladder</h3>
            <LadderBuilder
              stages={draft.stage_blueprint}
              onChange={(next) => updateDraft({ stage_blueprint: next })}
              defaultSLA={effectiveDefaultSla}
            />
          </div>
        </CardBody>
      </Card>

      <LadderSimulationWidget
        stageBlueprint={draft.stage_blueprint}
        defaultSla={draft.default_stage_sla_hours ?? null}
      />

      <Card>
        <CardBody className="space-y-3">
          <div>
            <h3 className="text-md font-semibold text-neutral-800">Assignments</h3>
            <p className="text-sm text-neutral-500">
              Map the template to teams or protocol templates. Leave one field blank if assigning
              to a specific target only.
            </p>
          </div>
          {assignError && <Alert variant="error">{assignError}</Alert>}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
            <Input
              label="Team ID"
              value={assignmentTarget.team_id}
              onChange={(event) =>
                setAssignmentTarget((prev) => ({ ...prev, team_id: event.target.value }))
              }
              placeholder="team uuid"
            />
            <Input
              label="Protocol template ID"
              value={assignmentTarget.protocol_template_id}
              onChange={(event) =>
                setAssignmentTarget((prev) => ({
                  ...prev,
                  protocol_template_id: event.target.value,
                }))
              }
              placeholder="protocol uuid"
            />
            <Button onClick={handleAssignmentSubmit} variant="secondary">
              Add assignment
            </Button>
          </div>
          <div className="space-y-2">
            {assignments.map((assignment) => (
              <div
                key={assignment.id}
                className="flex items-center justify-between rounded border border-neutral-200 px-4 py-3 text-sm"
              >
                <div className="space-y-1">
                  <p className="font-medium text-neutral-800">
                    Team: {assignment.team_id ?? '—'} · Protocol: {assignment.protocol_template_id ?? '—'}
                  </p>
                  <p className="text-xs text-neutral-500">
                    Assigned on {new Date(assignment.created_at).toLocaleString()}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  onClick={() => onDeleteAssignment(assignment.id)}
                >
                  Remove
                </Button>
              </div>
            ))}
            {assignments.length === 0 && (
              <p className="text-sm text-neutral-500">No assignments yet.</p>
            )}
          </div>
        </CardBody>
      </Card>
    </div>
  )
}
