'use client'

import React, { useEffect, useMemo, useState } from 'react'

import {
  useRepositories,
  useCreateRelease,
  useApproveRelease,
  useAddCollaborator,
  useRepositoryTimeline,
  useSharingReviewStream,
  useRequestFederationGrant,
  useDecideFederationGrant,
  useCreateReleaseChannel,
  usePublishReleaseChannelVersion,
} from '../hooks/useSharingWorkspace'
import type {
  DNARepository,
  DNARepositoryRelease,
  DNARepositoryReleaseChannel,
  DNARepositoryFederationLink,
  DNARepositoryFederationGrant,
} from '../types'

// purpose: render guarded DNA sharing workspace UI with release and guardrail workflows
// status: experimental

const initialReleaseForm = {
  version: '',
  title: '',
  notes: '',
  planner_session_id: '',
  mitigation_summary: '',
  custody_clear: true,
  lifecycle_snapshot: '{"source": "planner", "checkpoint": "final"}',
  mitigation_history: '[]',
  replay_checkpoint: '{"checkpoint": "final"}',
}

type ReleaseFormState = typeof initialReleaseForm

type CollaboratorFormState = {
  user_id: string
  role: 'viewer' | 'contributor' | 'maintainer' | 'owner'
}

export default function SharingWorkspacePage() {
  const { data: repositories } = useRepositories()
  const [selectedRepoId, setSelectedRepoId] = useState<string | null>(null)
  const [releaseForm, setReleaseForm] = useState<ReleaseFormState>(initialReleaseForm)
  const [collaboratorForm, setCollaboratorForm] = useState<CollaboratorFormState>({
    user_id: '',
    role: 'contributor',
  })
  const [activeReleaseId, setActiveReleaseId] = useState<string | null>(null)
  const [grantForms, setGrantForms] = useState<
    Record<string, { organization: string; permission_tier: 'reviewer' | 'publisher' | 'observer'; guardrail_scope: string }>
  >({})
  const [newChannelForm, setNewChannelForm] = useState({
    name: '',
    slug: '',
    description: '',
    audience_scope: 'partners' as 'internal' | 'partners' | 'public',
    guardrail_profile: '{"audience": "partners"}',
    federation_link_id: '',
  })
  const [channelVersionForms, setChannelVersionForms] = useState<Record<string, {
    release_id: string
    version_label: string
    guardrail_attestation: string
    provenance_snapshot: string
    mitigation_digest: string
    grant_id: string
  }>>({})

  const selectedRepo: DNARepository | undefined = useMemo(
    () => repositories?.find((repo) => repo.id === selectedRepoId) ?? repositories?.[0],
    [repositories, selectedRepoId],
  )

  const releaseMutation = useCreateRelease(selectedRepo?.id ?? '')
  const approvalMutation = useApproveRelease(selectedRepo?.id ?? null)
  const addCollaboratorMutation = useAddCollaborator(selectedRepo?.id ?? '')
  const requestGrantMutation = useRequestFederationGrant()
  const decideGrantMutation = useDecideFederationGrant()
  const createChannelMutation = useCreateReleaseChannel(selectedRepo?.id ?? '')
  const publishChannelMutation = usePublishReleaseChannelVersion()
  const { data: timeline } = useRepositoryTimeline(selectedRepo?.id ?? null)
  useSharingReviewStream(selectedRepo?.id ?? null)

  const releases: DNARepositoryRelease[] = selectedRepo?.releases ?? []
  const releaseChannels: DNARepositoryReleaseChannel[] = selectedRepo?.release_channels ?? []
  
  const getGrantForm = (linkId: string) =>
    grantForms[linkId] ?? { organization: '', permission_tier: 'reviewer', guardrail_scope: '{}' }

  const updateGrantForm = (
    linkId: string,
    updates: Partial<{ organization: string; permission_tier: 'reviewer' | 'publisher' | 'observer'; guardrail_scope: string }>,
  ) => {
    setGrantForms((prev) => ({ ...prev, [linkId]: { ...getGrantForm(linkId), ...updates } }))
  }

  const submitGrantRequest = (link: DNARepositoryFederationLink) => {
    const form = getGrantForm(link.id)
    let scope: Record<string, any> = {}
    try {
      scope = form.guardrail_scope ? JSON.parse(form.guardrail_scope) : {}
    } catch (error) {
      console.error('Failed to parse guardrail scope', error)
    }
    requestGrantMutation.mutate({
      linkId: link.id,
      organization: form.organization,
      permission_tier: form.permission_tier,
      guardrail_scope: scope,
    })
    setGrantForms((prev) => ({
      ...prev,
      [link.id]: { organization: '', permission_tier: 'reviewer', guardrail_scope: '{}' },
    }))
  }

  const submitGrantDecision = (grant: DNARepositoryFederationGrant, decision: 'approve' | 'revoke') => {
    decideGrantMutation.mutate({ id: grant.id, decision })
  }

  const submitChannelCreation = () => {
    if (!selectedRepo) return
    let guardrailProfile: Record<string, any> = {}
    try {
      guardrailProfile = newChannelForm.guardrail_profile
        ? JSON.parse(newChannelForm.guardrail_profile)
        : {}
    } catch (error) {
      console.error('Failed to parse channel guardrail profile', error)
    }
    createChannelMutation.mutate({
      name: newChannelForm.name,
      slug: newChannelForm.slug,
      description: newChannelForm.description || undefined,
      audience_scope: newChannelForm.audience_scope,
      guardrail_profile: guardrailProfile,
      federation_link_id: newChannelForm.federation_link_id || undefined,
    })
    setNewChannelForm({
      name: '',
      slug: '',
      description: '',
      audience_scope: 'partners',
      guardrail_profile: '{"audience": "partners"}',
      federation_link_id: '',
    })
  }

  const getChannelVersionForm = (channelId: string) =>
    channelVersionForms[channelId] ?? {
      release_id: activeRelease?.id ?? '',
      version_label: '',
      guardrail_attestation: '{}',
      provenance_snapshot: '{}',
      mitigation_digest: '',
      grant_id: '',
    }

  const updateChannelVersionForm = (
    channelId: string,
    updates: Partial<{
      release_id: string
      version_label: string
      guardrail_attestation: string
      provenance_snapshot: string
      mitigation_digest: string
      grant_id: string
    }>,
  ) => {
    setChannelVersionForms((prev) => ({
      ...prev,
      [channelId]: { ...getChannelVersionForm(channelId), ...updates },
    }))
  }

  const submitChannelVersion = (channelId: string) => {
    const form = getChannelVersionForm(channelId)
    let attestation: Record<string, any> = {}
    let provenance: Record<string, any> = {}
    try {
      attestation = form.guardrail_attestation ? JSON.parse(form.guardrail_attestation) : {}
    } catch (error) {
      console.error('Failed to parse guardrail attestation JSON', error)
    }
    try {
      provenance = form.provenance_snapshot ? JSON.parse(form.provenance_snapshot) : {}
    } catch (error) {
      console.error('Failed to parse provenance snapshot JSON', error)
    }
    publishChannelMutation.mutate({
      channelId,
      release_id: form.release_id || activeRelease?.id || '',
      version_label: form.version_label || `v${new Date().toISOString()}`,
      guardrail_attestation: attestation,
      provenance_snapshot: provenance,
      mitigation_digest: form.mitigation_digest || null,
      grant_id: form.grant_id || null,
    })
    setChannelVersionForms((prev) => ({
      ...prev,
      [channelId]: {
        release_id: activeRelease?.id ?? '',
        version_label: '',
        guardrail_attestation: '{}',
        provenance_snapshot: '{}',
        mitigation_digest: '',
        grant_id: '',
      },
    }))
  }

  useEffect(() => {
    if (selectedRepo && selectedRepo.releases.length > 0) {
      setActiveReleaseId((current) => current ?? selectedRepo.releases[0]?.id ?? null)
    } else {
      setActiveReleaseId(null)
    }
  }, [selectedRepo?.id])

  const activeRelease = useMemo(() => {
    if (!releases || releases.length === 0) return undefined
    const fromSelection = releases.find((release) => release.id === activeReleaseId)
    return fromSelection ?? releases[0]
  }, [releases, activeReleaseId])

  const previousRelease = useMemo(() => {
    if (!activeRelease) return undefined
    const index = releases.findIndex((release) => release.id === activeRelease.id)
    return index >= 0 && index + 1 < releases.length ? releases[index + 1] : undefined
  }, [releases, activeRelease])

  const guardrailDiff = useMemo(() => {
    if (!activeRelease) return [] as { key: string; before: string | null; after: string | null }[]
    const currentSnapshot = activeRelease.guardrail_snapshot ?? {}
    const previousSnapshot = previousRelease?.guardrail_snapshot ?? {}
    const keys = Array.from(
      new Set([...Object.keys(previousSnapshot ?? {}), ...Object.keys(currentSnapshot ?? {})]),
    )
    return keys
      .map((key) => {
        const before = previousSnapshot ? JSON.stringify(previousSnapshot[key]) : null
        const after = JSON.stringify(currentSnapshot[key])
        return { key, before, after }
      })
      .filter((entry) => entry.before !== entry.after)
  }, [activeRelease, previousRelease])

  const submitRelease = () => {
    if (!selectedRepo) return
    let lifecycleSnapshot: Record<string, any> = {}
    let mitigationHistory: Record<string, any>[] = []
    let replayCheckpoint: Record<string, any> = {}
    try {
      lifecycleSnapshot = releaseForm.lifecycle_snapshot
        ? JSON.parse(releaseForm.lifecycle_snapshot)
        : {}
    } catch (error) {
      console.error('Failed to parse lifecycle snapshot JSON', error)
    }
    try {
      const parsed = releaseForm.mitigation_history
        ? JSON.parse(releaseForm.mitigation_history)
        : []
      mitigationHistory = Array.isArray(parsed) ? parsed : []
    } catch (error) {
      console.error('Failed to parse mitigation history JSON', error)
    }
    try {
      replayCheckpoint = releaseForm.replay_checkpoint
        ? JSON.parse(releaseForm.replay_checkpoint)
        : {}
    } catch (error) {
      console.error('Failed to parse replay checkpoint JSON', error)
    }
    releaseMutation.mutate({
      version: releaseForm.version,
      title: releaseForm.title,
      notes: releaseForm.notes || null,
      mitigation_summary: releaseForm.mitigation_summary || null,
      planner_session_id: releaseForm.planner_session_id || null,
      guardrail_snapshot: {
        custody_status: releaseForm.custody_clear ? 'clear' : 'halted',
        breaches: releaseForm.custody_clear ? [] : ['custody.blocked'],
      },
      lifecycle_snapshot: lifecycleSnapshot,
      mitigation_history: mitigationHistory,
      replay_checkpoint: replayCheckpoint,
    })
    setReleaseForm(initialReleaseForm)
  }

  const approveRelease = (release: DNARepositoryRelease) => {
    approvalMutation.mutate({
      id: release.id,
      data: { status: 'approved', guardrail_flags: [], notes: 'Approved from workspace' },
    })
  }

  const submitCollaborator = () => {
    if (!selectedRepo || !collaboratorForm.user_id) return
    addCollaboratorMutation.mutate({
      user_id: collaboratorForm.user_id,
      role: collaboratorForm.role,
    })
    setCollaboratorForm({ user_id: '', role: 'contributor' })
  }

  return (
    <div className="grid gap-6 md:grid-cols-[280px_1fr]">
      <aside className="space-y-4">
        <h1 className="text-xl font-semibold">DNA Sharing Repositories</h1>
        <ul className="space-y-2">
          {repositories?.map((repo) => (
            <li
              key={repo.id}
              className={`rounded border p-3 text-sm shadow-sm transition hover:border-blue-400 ${
                repo.id === selectedRepo?.id ? 'border-blue-500 bg-blue-50' : 'border-slate-200'
              }`}
              onClick={() => setSelectedRepoId(repo.id)}
            >
              <div className="font-medium">{repo.name}</div>
              <div className="text-xs text-slate-600">{repo.guardrail_policy.name}</div>
            </li>
          ))}
        </ul>
        {selectedRepo && (
          <section className="rounded border border-slate-200 p-3">
            <h2 className="mb-2 text-sm font-semibold uppercase text-slate-600">Guardrail Policy</h2>
            <dl className="space-y-1 text-xs text-slate-700">
              <div className="flex justify-between">
                <dt>Approvals Required</dt>
                <dd>{selectedRepo.guardrail_policy.approval_threshold}</dd>
              </div>
              <div className="flex justify-between">
                <dt>Custody Clearance</dt>
                <dd>{selectedRepo.guardrail_policy.requires_custody_clearance ? 'Required' : 'Optional'}</dd>
              </div>
              <div className="flex justify-between">
                <dt>Planner Link</dt>
                <dd>{selectedRepo.guardrail_policy.requires_planner_link ? 'Required' : 'Optional'}</dd>
              </div>
            </dl>
            {selectedRepo.guardrail_policy.mitigation_playbooks.length > 0 && (
              <div className="mt-3">
                <p className="text-xs font-semibold text-slate-600">Mitigation Playbooks</p>
                <ul className="mt-1 space-y-1 text-xs text-slate-700">
                  {selectedRepo.guardrail_policy.mitigation_playbooks.map((item) => (
                    <li key={item} className="rounded bg-slate-100 px-2 py-1">
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </section>
        )}
      </aside>
      <main className="space-y-6">
        {selectedRepo ? (
          <div className="space-y-6">
            <section className="rounded border border-slate-200 p-4 shadow-sm">
              <header className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">{selectedRepo.name}</h2>
                  <p className="text-sm text-slate-600">{selectedRepo.description || 'No description provided.'}</p>
                </div>
                <div className="text-xs text-slate-500">
                  Updated {new Date(selectedRepo.updated_at).toLocaleString()}
                </div>
              </header>
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <h3 className="mb-2 text-sm font-semibold text-slate-600">Collaborators</h3>
                  <ul className="space-y-2 text-sm">
                    {selectedRepo.collaborators.map((collab) => (
                      <li key={collab.id} className="flex justify-between rounded border border-slate-200 px-2 py-1">
                        <span>{collab.user_id}</span>
                        <span className="text-xs uppercase text-slate-500">{collab.role}</span>
                      </li>
                    ))}
                    {selectedRepo.collaborators.length === 0 && (
                      <li className="text-xs text-slate-500">No collaborators yet.</li>
                    )}
                  </ul>
                  <div className="mt-3 space-y-2 text-xs">
                    <input
                      className="w-full rounded border border-slate-300 px-2 py-1"
                      placeholder="Collaborator user ID"
                      value={collaboratorForm.user_id}
                      onChange={(event) => setCollaboratorForm((prev) => ({ ...prev, user_id: event.target.value }))}
                    />
                    <select
                      className="w-full rounded border border-slate-300 px-2 py-1"
                      value={collaboratorForm.role}
                      onChange={(event) =>
                        setCollaboratorForm((prev) => ({ ...prev, role: event.target.value as CollaboratorFormState['role'] }))
                      }
                    >
                      <option value="viewer">Viewer</option>
                      <option value="contributor">Contributor</option>
                      <option value="maintainer">Maintainer</option>
                      <option value="owner">Owner</option>
                    </select>
                    <button
                      className="w-full rounded bg-blue-600 px-3 py-1 text-white"
                      onClick={submitCollaborator}
                    >
                      Invite Collaborator
                    </button>
                  </div>
                </div>
                  <div>
                    <h3 className="mb-2 text-sm font-semibold text-slate-600">Create Release</h3>
                    <div className="space-y-2 text-xs">
                    <input
                      className="w-full rounded border border-slate-300 px-2 py-1"
                      placeholder="Version (e.g. v1.0.0)"
                      value={releaseForm.version}
                      onChange={(event) => setReleaseForm((prev) => ({ ...prev, version: event.target.value }))}
                    />
                    <input
                      className="w-full rounded border border-slate-300 px-2 py-1"
                      placeholder="Title"
                      value={releaseForm.title}
                      onChange={(event) => setReleaseForm((prev) => ({ ...prev, title: event.target.value }))}
                    />
                    <textarea
                      className="h-20 w-full rounded border border-slate-300 px-2 py-1"
                      placeholder="Notes"
                      value={releaseForm.notes}
                      onChange={(event) => setReleaseForm((prev) => ({ ...prev, notes: event.target.value }))}
                    />
                      <textarea
                        className="h-20 w-full rounded border border-slate-300 px-2 py-1"
                        placeholder="Mitigation summary"
                        value={releaseForm.mitigation_summary}
                        onChange={(event) =>
                          setReleaseForm((prev) => ({ ...prev, mitigation_summary: event.target.value }))
                        }
                      />
                      <textarea
                        className="h-20 w-full rounded border border-slate-300 px-2 py-1"
                        placeholder='Lifecycle snapshot JSON (e.g. {"source": "planner"})'
                        value={releaseForm.lifecycle_snapshot}
                        onChange={(event) =>
                          setReleaseForm((prev) => ({ ...prev, lifecycle_snapshot: event.target.value }))
                        }
                      />
                      <textarea
                        className="h-20 w-full rounded border border-slate-300 px-2 py-1"
                        placeholder='Mitigation history JSON array (e.g. [{"action": "custody-clear"}])'
                        value={releaseForm.mitigation_history}
                        onChange={(event) =>
                          setReleaseForm((prev) => ({ ...prev, mitigation_history: event.target.value }))
                        }
                      />
                      <textarea
                        className="h-20 w-full rounded border border-slate-300 px-2 py-1"
                        placeholder='Replay checkpoint JSON (e.g. {"checkpoint": "final"})'
                        value={releaseForm.replay_checkpoint}
                        onChange={(event) =>
                          setReleaseForm((prev) => ({ ...prev, replay_checkpoint: event.target.value }))
                        }
                      />
                      <input
                        className="w-full rounded border border-slate-300 px-2 py-1"
                        placeholder="Planner session ID"
                        value={releaseForm.planner_session_id}
                        onChange={(event) =>
                        setReleaseForm((prev) => ({ ...prev, planner_session_id: event.target.value }))
                      }
                    />
                    <label className="flex items-center space-x-2 text-slate-600">
                      <input
                        type="checkbox"
                        checked={releaseForm.custody_clear}
                        onChange={(event) =>
                          setReleaseForm((prev) => ({ ...prev, custody_clear: event.target.checked }))
                        }
                      />
                      <span>Custody guardrails cleared</span>
                    </label>
                    <button
                      className="w-full rounded bg-emerald-600 px-3 py-1 text-white"
                      onClick={submitRelease}
                      disabled={releaseMutation.isPending}
                    >
                      Queue Release for Approval
                    </button>
                  </div>
                </div>
              </div>
            </section>

              <section className="rounded border border-slate-200 p-4 shadow-sm">
                <h3 className="mb-3 text-lg font-semibold">Releases</h3>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-left text-sm">
                  <thead className="bg-slate-100 text-xs uppercase tracking-wide text-slate-600">
                    <tr>
                      <th className="px-3 py-2">Version</th>
                      <th className="px-3 py-2">Status</th>
                      <th className="px-3 py-2">Guardrail</th>
                      <th className="px-3 py-2">Approvals</th>
                      <th className="px-3 py-2">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                      {releases.map((release) => (
                        <tr
                          key={release.id}
                          className={`border-b border-slate-200 ${
                            release.id === activeRelease?.id ? 'bg-blue-50' : ''
                          }`}
                          onClick={() => setActiveReleaseId(release.id)}
                        >
                          <td className="px-3 py-2 font-medium">{release.version}</td>
                        <td className="px-3 py-2 capitalize">{release.status.replace('_', ' ')}</td>
                        <td className="px-3 py-2">
                          <span
                            className={`rounded px-2 py-1 text-xs font-semibold ${
                              release.guardrail_state === 'cleared'
                                ? 'bg-emerald-100 text-emerald-700'
                                : release.guardrail_state === 'requires_mitigation'
                                ? 'bg-amber-100 text-amber-700'
                                : 'bg-rose-100 text-rose-700'
                            }`}
                          >
                            {release.guardrail_state}
                          </span>
                        </td>
                        <td className="px-3 py-2 text-xs text-slate-600">
                          {release.approvals.length > 0 ? (
                            <ul className="space-y-1">
                              {release.approvals.map((approval) => (
                                <li key={approval.id}>
                                  {approval.status} · {approval.approver_id}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <span>No approvals</span>
                          )}
                        </td>
                        <td className="px-3 py-2">
                          {release.status !== 'published' && (
                            <button
                              className="rounded bg-blue-600 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-white"
                              onClick={() => approveRelease(release)}
                              disabled={approvalMutation.isPending}
                            >
                              Approve
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                    {releases.length === 0 && (
                      <tr>
                        <td className="px-3 py-2 text-sm text-slate-500" colSpan={5}>
                          No releases yet. Create one to kick off guardrail approvals.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
                </div>
              </section>

              {activeRelease && (
                <section className="rounded border border-slate-200 p-4 shadow-sm">
                  <header className="mb-3 flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h3 className="text-lg font-semibold">Active Release Review</h3>
                      <p className="text-sm text-slate-600">
                        Comparing guardrail state with previous release to support inline review sessions.
                      </p>
                    </div>
                    <div className="flex items-center space-x-2 text-xs uppercase tracking-wide text-slate-500">
                      <span className="inline-flex items-center space-x-1 rounded-full bg-emerald-100 px-2 py-1 font-semibold text-emerald-700">
                        <span className="h-2 w-2 rounded-full bg-emerald-500" aria-hidden />
                        <span>Live stream</span>
                      </span>
                      <span>{new Date(activeRelease.updated_at).toLocaleString()}</span>
                    </div>
                  </header>
                  <div className="grid gap-4 lg:grid-cols-3">
                    <div className="rounded border border-slate-200 p-3">
                      <h4 className="text-sm font-semibold text-slate-600">Guardrail Snapshot Diff</h4>
                      {guardrailDiff.length > 0 ? (
                        <ul className="mt-2 space-y-2 text-xs text-slate-700">
                          {guardrailDiff.map((entry) => (
                            <li key={entry.key} className="rounded border border-slate-100 p-2">
                              <p className="font-semibold">{entry.key}</p>
                              <p className="text-rose-600">Before: {entry.before ?? '—'}</p>
                              <p className="text-emerald-600">After: {entry.after ?? '—'}</p>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="mt-2 text-xs text-slate-500">No guardrail changes detected.</p>
                      )}
                    </div>
                    <div className="rounded border border-slate-200 p-3">
                      <h4 className="text-sm font-semibold text-slate-600">Lifecycle Snapshot</h4>
                      <pre className="mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap break-all text-xs text-slate-700">
                        {JSON.stringify(activeRelease.lifecycle_snapshot, null, 2)}
                      </pre>
                    </div>
                    <div className="rounded border border-slate-200 p-3">
                      <h4 className="text-sm font-semibold text-slate-600">Replay Checkpoint</h4>
                      <pre className="mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap break-all text-xs text-slate-700">
                        {JSON.stringify(activeRelease.replay_checkpoint, null, 2)}
                      </pre>
                    </div>
                  </div>
                  <div className="mt-4 rounded border border-slate-200 p-3">
                    <h4 className="text-sm font-semibold text-slate-600">Mitigation History</h4>
                    {activeRelease.mitigation_history.length > 0 ? (
                      <ol className="mt-2 space-y-2 text-xs text-slate-700">
                        {activeRelease.mitigation_history.map((entry, index) => (
                          <li key={index} className="rounded border border-slate-100 p-2">
                            <span className="font-semibold">Step {index + 1}</span>
                            <pre className="mt-1 whitespace-pre-wrap break-all">
                              {JSON.stringify(entry, null, 2)}
                            </pre>
                          </li>
                        ))}
                      </ol>
                    ) : (
                      <p className="mt-2 text-xs text-slate-500">No mitigation actions recorded.</p>
                    )}
                  </div>
                </section>
              )}

              <section className="rounded border border-slate-200 p-4 shadow-sm">
                <h3 className="mb-3 text-lg font-semibold">Federated Collaborations</h3>
                {selectedRepo.federation_links.length > 0 ? (
                  <div className="grid gap-4 md:grid-cols-2">
                    {selectedRepo.federation_links.map((link) => {
                      const form = getGrantForm(link.id)
                      return (
                        <div key={link.id} className="rounded border border-slate-200 p-3 text-xs">
                          <header className="mb-2 flex items-center justify-between text-sm font-semibold text-slate-700">
                            <span>{link.external_organization}</span>
                            <span className="rounded bg-slate-100 px-2 py-1 text-xs uppercase">{link.trust_state}</span>
                          </header>
                          <p className="text-slate-600">External repository: {link.external_repository_id}</p>
                          <p className="mt-1 text-slate-500">
                            Guardrail contract: {JSON.stringify(link.guardrail_contract)}
                          </p>
                          <div className="mt-3 space-y-2">
                            <input
                              className="w-full rounded border border-slate-300 px-2 py-1"
                              placeholder="Partner organization"
                              value={form.organization}
                              onChange={(event) =>
                                updateGrantForm(link.id, { organization: event.target.value })
                              }
                            />
                            <select
                              className="w-full rounded border border-slate-300 px-2 py-1"
                              value={form.permission_tier}
                              onChange={(event) =>
                                updateGrantForm(link.id, {
                                  permission_tier: event.target.value as 'reviewer' | 'publisher' | 'observer',
                                })
                              }
                            >
                              <option value="reviewer">Reviewer</option>
                              <option value="publisher">Publisher</option>
                              <option value="observer">Observer</option>
                            </select>
                            <textarea
                              className="h-16 w-full rounded border border-slate-300 px-2 py-1"
                              placeholder='Guardrail scope JSON (e.g. {"allowed": ["qc"]})'
                              value={form.guardrail_scope}
                              onChange={(event) =>
                                updateGrantForm(link.id, { guardrail_scope: event.target.value })
                              }
                            />
                            <button
                              className="w-full rounded bg-blue-600 px-3 py-1 font-semibold uppercase text-white"
                              onClick={() => submitGrantRequest(link)}
                              disabled={requestGrantMutation.isPending}
                            >
                              Request Grant
                            </button>
                          </div>
                          <div className="mt-4">
                            <h4 className="text-xs font-semibold uppercase text-slate-500">Grants</h4>
                            <ul className="mt-2 space-y-2">
                              {link.grants.map((grant) => (
                                <li key={grant.id} className="rounded border border-slate-100 p-2">
                                  <div className="flex items-center justify-between">
                                    <span className="font-semibold">{grant.organization}</span>
                                    <span>{grant.permission_tier}</span>
                                  </div>
                                  <p className="mt-1 text-slate-500">State: {grant.handshake_state}</p>
                                  <p className="mt-1 text-slate-500">
                                    Guardrail scope: {JSON.stringify(grant.guardrail_scope)}
                                  </p>
                                  <div className="mt-2 flex gap-2">
                                    {grant.handshake_state !== 'active' && (
                                      <button
                                        className="flex-1 rounded bg-emerald-600 px-3 py-1 text-white"
                                        onClick={() => submitGrantDecision(grant, 'approve')}
                                        disabled={decideGrantMutation.isPending}
                                      >
                                        Approve
                                      </button>
                                    )}
                                    {grant.handshake_state === 'active' && (
                                      <button
                                        className="flex-1 rounded bg-rose-600 px-3 py-1 text-white"
                                        onClick={() => submitGrantDecision(grant, 'revoke')}
                                        disabled={decideGrantMutation.isPending}
                                      >
                                        Revoke
                                      </button>
                                    )}
                                  </div>
                                </li>
                              ))}
                              {link.grants.length === 0 && (
                                <li className="text-slate-500">No federated grants yet.</li>
                              )}
                            </ul>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500">No federation links established yet. Use the API to connect partner labs.</p>
                )}
              </section>

              <section className="rounded border border-slate-200 p-4 shadow-sm">
                <h3 className="mb-3 text-lg font-semibold">Release Channels</h3>
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="rounded border border-dashed border-slate-300 p-3 text-xs">
                    <h4 className="text-sm font-semibold text-slate-700">Create Channel</h4>
                    <input
                      className="mt-2 w-full rounded border border-slate-300 px-2 py-1"
                      placeholder="Channel name"
                      value={newChannelForm.name}
                      onChange={(event) => setNewChannelForm((prev) => ({ ...prev, name: event.target.value }))}
                    />
                    <input
                      className="mt-2 w-full rounded border border-slate-300 px-2 py-1"
                      placeholder="Slug"
                      value={newChannelForm.slug}
                      onChange={(event) => setNewChannelForm((prev) => ({ ...prev, slug: event.target.value }))}
                    />
                    <textarea
                      className="mt-2 h-16 w-full rounded border border-slate-300 px-2 py-1"
                      placeholder="Description"
                      value={newChannelForm.description}
                      onChange={(event) => setNewChannelForm((prev) => ({ ...prev, description: event.target.value }))}
                    />
                    <select
                      className="mt-2 w-full rounded border border-slate-300 px-2 py-1"
                      value={newChannelForm.audience_scope}
                      onChange={(event) =>
                        setNewChannelForm((prev) => ({
                          ...prev,
                          audience_scope: event.target.value as 'internal' | 'partners' | 'public',
                        }))
                      }
                    >
                      <option value="internal">Internal</option>
                      <option value="partners">Partners</option>
                      <option value="public">Public</option>
                    </select>
                    <textarea
                      className="mt-2 h-20 w-full rounded border border-slate-300 px-2 py-1"
                      placeholder='Guardrail profile JSON (e.g. {"audience": "partners"})'
                      value={newChannelForm.guardrail_profile}
                      onChange={(event) => setNewChannelForm((prev) => ({ ...prev, guardrail_profile: event.target.value }))}
                    />
                    <input
                      className="mt-2 w-full rounded border border-slate-300 px-2 py-1"
                      placeholder="Federation link ID (optional)"
                      value={newChannelForm.federation_link_id}
                      onChange={(event) => setNewChannelForm((prev) => ({ ...prev, federation_link_id: event.target.value }))}
                    />
                    <button
                      className="mt-3 w-full rounded bg-blue-600 px-3 py-1 font-semibold uppercase text-white"
                      onClick={submitChannelCreation}
                      disabled={createChannelMutation.isPending}
                    >
                      Create Channel
                    </button>
                  </div>
                  <div className="md:col-span-2">
                    {releaseChannels.length > 0 ? (
                      <div className="grid gap-4 md:grid-cols-2">
                        {releaseChannels.map((channel) => {
                          const form = getChannelVersionForm(channel.id)
                          return (
                            <div key={channel.id} className="rounded border border-slate-200 p-3 text-xs">
                              <header className="mb-2 flex items-center justify-between text-sm font-semibold text-slate-700">
                                <span>{channel.name}</span>
                                <span className="rounded bg-slate-100 px-2 py-1 text-xs uppercase">{channel.audience_scope}</span>
                              </header>
                              <p className="text-slate-600">{channel.description || 'No description provided.'}</p>
                              {channel.federation_link_id && (
                                <p className="mt-1 text-slate-500">Federation link: {channel.federation_link_id}</p>
                              )}
                              <div className="mt-3 space-y-2">
                                <select
                                  className="w-full rounded border border-slate-300 px-2 py-1"
                                  value={form.release_id}
                                  onChange={(event) =>
                                    updateChannelVersionForm(channel.id, { release_id: event.target.value })
                                  }
                                >
                                  <option value="">Select release</option>
                                  {releases.map((release) => (
                                    <option key={release.id} value={release.id}>
                                      {release.version}
                                    </option>
                                  ))}
                                </select>
                                <input
                                  className="w-full rounded border border-slate-300 px-2 py-1"
                                  placeholder="Version label"
                                  value={form.version_label}
                                  onChange={(event) =>
                                    updateChannelVersionForm(channel.id, { version_label: event.target.value })
                                  }
                                />
                                <textarea
                                  className="h-16 w-full rounded border border-slate-300 px-2 py-1"
                                  placeholder='Guardrail attestation JSON (e.g. {"status": "cleared"})'
                                  value={form.guardrail_attestation}
                                  onChange={(event) =>
                                    updateChannelVersionForm(channel.id, { guardrail_attestation: event.target.value })
                                  }
                                />
                                <textarea
                                  className="h-16 w-full rounded border border-slate-300 px-2 py-1"
                                  placeholder='Provenance snapshot JSON (e.g. {"source": "planner"})'
                                  value={form.provenance_snapshot}
                                  onChange={(event) =>
                                    updateChannelVersionForm(channel.id, { provenance_snapshot: event.target.value })
                                  }
                                />
                                <input
                                  className="w-full rounded border border-slate-300 px-2 py-1"
                                  placeholder="Mitigation digest"
                                  value={form.mitigation_digest}
                                  onChange={(event) =>
                                    updateChannelVersionForm(channel.id, { mitigation_digest: event.target.value })
                                  }
                                />
                                <input
                                  className="w-full rounded border border-slate-300 px-2 py-1"
                                  placeholder="Federation grant ID (optional)"
                                  value={form.grant_id}
                                  onChange={(event) =>
                                    updateChannelVersionForm(channel.id, { grant_id: event.target.value })
                                  }
                                />
                                <button
                                  className="w-full rounded bg-emerald-600 px-3 py-1 font-semibold uppercase text-white"
                                  onClick={() => submitChannelVersion(channel.id)}
                                  disabled={publishChannelMutation.isPending}
                                >
                                  Publish to Channel
                                </button>
                              </div>
                              <ul className="mt-4 space-y-2 text-slate-700">
                                {channel.versions.map((version) => {
                                  const grant = selectedRepo?.federation_links
                                    .flatMap((link) => link.grants)
                                    .find((entry) => entry.id === version.grant_id)
                                  return (
                                    <li key={version.id} className="rounded border border-slate-100 p-2">
                                      <div className="flex items-center justify-between text-xs">
                                        <span className="font-semibold">{version.version_label}</span>
                                        <span>Seq {version.sequence}</span>
                                      </div>
                                      <p className="mt-1 text-slate-500">
                                        Provenance: {JSON.stringify(version.provenance_snapshot)}
                                      </p>
                                      {version.mitigation_digest && (
                                        <p className="mt-1 text-slate-500">Mitigation: {version.mitigation_digest}</p>
                                      )}
                                      {grant && (
                                        <p className="mt-1 text-slate-500">
                                          Grant: {grant.organization} · {grant.permission_tier} ({grant.handshake_state})
                                        </p>
                                      )}
                                    </li>
                                  )
                                })}
                                {channel.versions.length === 0 && (
                                  <li className="text-slate-500">No published versions yet.</li>
                                )}
                              </ul>
                            </div>
                          )
                        })}
                      </div>
                    ) : (
                      <p className="text-sm text-slate-500">No channels created yet. Define a channel to publish collaborative releases.</p>
                    )}
                  </div>
                </div>
              </section>

              <section className="rounded border border-slate-200 p-4 shadow-sm">
                <h3 className="mb-3 text-lg font-semibold">Timeline</h3>
                <ul className="space-y-2 text-sm">
                {timeline?.map((event) => (
                  <li key={event.id} className="rounded border border-slate-200 px-3 py-2">
                      <div className="flex items-center justify-between text-xs text-slate-500">
                        <span className="font-semibold uppercase">{event.event_type}</span>
                        <span>{new Date(event.created_at).toLocaleString()}</span>
                      </div>
                      {event.release_id && (
                        <p className="mt-1 text-xs text-slate-600">Release: {event.release_id}</p>
                      )}
                      <pre className="mt-2 whitespace-pre-wrap break-all text-xs text-slate-700">
                        {JSON.stringify(event.payload, null, 2)}
                      </pre>
                    </li>
                  ))}
                {(!timeline || timeline.length === 0) && (
                  <li className="text-xs text-slate-500">No timeline events recorded yet.</li>
                )}
              </ul>
            </section>
          </div>
        ) : (
          <div className="rounded border border-dashed border-slate-300 p-12 text-center text-slate-500">
            Create a DNA repository to start managing guardrail-aware releases.
          </div>
        )}
      </main>
    </div>
  )
}
