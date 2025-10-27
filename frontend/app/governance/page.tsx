'use client'
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import TemplateLibrary from '../components/governance/TemplateLibrary'
import TemplateEditor from '../components/governance/TemplateEditor'
import {
  useGovernanceTemplates,
  useGovernanceTemplate,
  useCreateGovernanceTemplate,
  useGovernanceAssignments,
  useCreateGovernanceAssignment,
  useDeleteGovernanceAssignment,
} from '../hooks/useGovernance'
import type {
  GovernanceTemplate,
  GovernanceTemplateDraft,
  GovernanceTemplateAssignment,
} from '../types'
import { EmptyState } from '../components/ui'

const emptyDraft = (): GovernanceTemplateDraft => ({
  template_key: '',
  name: '',
  description: '',
  default_stage_sla_hours: undefined,
  permitted_roles: [],
  stage_blueprint: [],
  forked_from_id: undefined,
  publish: false,
})

const draftFromTemplate = (template: GovernanceTemplate): GovernanceTemplateDraft => ({
  template_key: template.template_key,
  name: template.name,
  description: template.description ?? '',
  default_stage_sla_hours: template.default_stage_sla_hours ?? undefined,
  permitted_roles: [...template.permitted_roles],
  stage_blueprint: template.stage_blueprint.map((stage) => ({
    name: stage.name ?? undefined,
    required_role: stage.required_role,
    sla_hours: stage.sla_hours ?? undefined,
    metadata: stage.metadata ? { ...stage.metadata } : {},
  })),
  forked_from_id: template.id,
  publish: false,
})

// purpose: governance admin landing page combining library and editor
// inputs: governance hooks for templates and assignments
// outputs: interactive workspace for authoring and publishing ladders
// status: experimental
export default function GovernanceWorkspacePage() {
  const [selectedTemplateId, setSelectedTemplateId] = useState<string | null>(null)
  const [draft, setDraft] = useState<GovernanceTemplateDraft>(emptyDraft)
  const [activeTemplate, setActiveTemplate] = useState<GovernanceTemplate | null>(null)
  const [assignError, setAssignError] = useState<string | null>(null)
  const selectedTemplateRef = useRef<string | null>(null)
  const forkSourceRef = useRef<string | null>(null)

  const templatesQuery = useGovernanceTemplates(true)
  const templateQuery = useGovernanceTemplate(selectedTemplateId ?? undefined)
  const assignmentsQuery = useGovernanceAssignments(selectedTemplateId ?? undefined)
  const createTemplate = useCreateGovernanceTemplate()
  const createAssignment = useCreateGovernanceAssignment()
  const deleteAssignment = useDeleteGovernanceAssignment()

  useEffect(() => {
    if (templateQuery.data) {
      setActiveTemplate(templateQuery.data)
      setDraft(draftFromTemplate(templateQuery.data))
      forkSourceRef.current = templateQuery.data.id
    }
  }, [templateQuery.data])

  const handleCreateNew = useCallback(() => {
    setSelectedTemplateId(null)
    setActiveTemplate(null)
    setDraft(emptyDraft())
    setAssignError(null)
    selectedTemplateRef.current = null
    forkSourceRef.current = null
  }, [])

  const handleSelectTemplate = useCallback((templateId: string | null) => {
    setSelectedTemplateId(templateId)
    setAssignError(null)
    selectedTemplateRef.current = templateId
    forkSourceRef.current = templateId
  }, [])

  const handleForkTemplate = useCallback((template: GovernanceTemplate) => {
    setSelectedTemplateId(template.id)
    setActiveTemplate(template)
    setDraft(draftFromTemplate(template))
    setAssignError(null)
    selectedTemplateRef.current = template.id
    forkSourceRef.current = template.id
  }, [])

  const handleDraftChange = useCallback(
    (
      next:
        | GovernanceTemplateDraft
        | ((current: GovernanceTemplateDraft) => GovernanceTemplateDraft),
    ) => {
      if (typeof next === 'function') {
        setDraft((current) => next(current))
      } else {
        setDraft(next)
      }
    },
    [],
  )

  const handlePersist = useCallback(
    async (publish: boolean) => {
      setAssignError(null)
      const payload: GovernanceTemplateDraft = {
        ...draft,
        publish,
        forked_from_id:
          draft.forked_from_id ??
          forkSourceRef.current ??
          activeTemplate?.id ??
          selectedTemplateRef.current ??
          selectedTemplateId ??
          undefined,
      }
      const result = await createTemplate.mutateAsync(payload)
      setSelectedTemplateId(result.id)
      setActiveTemplate(result)
      setDraft(draftFromTemplate(result))
      forkSourceRef.current = result.id
    },
    [activeTemplate, createTemplate, draft, selectedTemplateId]
  )

  const handleSaveDraft = useCallback(() => handlePersist(false), [handlePersist])
  const handlePublish = useCallback(() => handlePersist(true), [handlePersist])

  const handleCreateAssignment = useCallback(
    (target: { team_id?: string | null; protocol_template_id?: string | null }) => {
      if (!selectedTemplateId) {
        setAssignError('Save the template before adding assignments.')
        return
      }
      createAssignment.mutate({
        template_id: selectedTemplateId,
        team_id: target.team_id ?? undefined,
        protocol_template_id: target.protocol_template_id ?? undefined,
      })
    },
    [createAssignment, selectedTemplateId]
  )

  const handleDeleteAssignment = useCallback(
    (assignmentId: string) => {
      if (!selectedTemplateId) return
      deleteAssignment.mutate({ assignmentId, templateId: selectedTemplateId })
    },
    [deleteAssignment, selectedTemplateId]
  )

  const assignments: GovernanceTemplateAssignment[] = useMemo(
    () => assignmentsQuery.data ?? [],
    [assignmentsQuery.data]
  )

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <div className="lg:col-span-2">
        <TemplateLibrary
          templates={templatesQuery.data ?? []}
          isLoading={templatesQuery.isLoading}
          onSelect={handleSelectTemplate}
          onCreateNew={handleCreateNew}
          onFork={handleForkTemplate}
          selectedTemplateId={selectedTemplateId}
        />
      </div>
      <div className="lg:col-span-3">
        {draft ? (
          <TemplateEditor
            draft={draft}
            template={activeTemplate}
            onDraftChange={handleDraftChange}
            onSaveDraft={handleSaveDraft}
            onPublish={handlePublish}
            onCancel={handleCreateNew}
            assignments={assignments}
            onCreateAssignment={handleCreateAssignment}
            onDeleteAssignment={handleDeleteAssignment}
            isSaving={createTemplate.isPending}
            assignError={assignError}
          />
        ) : (
          <EmptyState
            title="Select a template"
            description="Choose a workflow template from the library or create a new one to begin."
          />
        )}
      </div>
    </div>
  )
}
