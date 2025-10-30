'use client'

import { useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import api from '../api/client'
import type {
  DNARepository,
  DNARepositoryFederationGrant,
  DNARepositoryFederationLink,
  DNARepositoryRelease,
  DNARepositoryReleaseChannel,
  DNARepositoryTimelineEvent,
} from '../types'

// purpose: provide guardrail-aware data hooks for the sharing workspace UI
// status: experimental

const repositoryKey = ['sharing', 'repositories'] as const

export const useRepositories = () => {
  return useQuery({
    queryKey: repositoryKey,
    queryFn: async () => {
      const resp = await api.get('/api/sharing/repositories')
      return resp.data as DNARepository[]
    },
  })
}

export const useCreateRepository = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Partial<DNARepository>) => api.post('/api/sharing/repositories', data),
    onSuccess: () => qc.invalidateQueries({ queryKey: repositoryKey }),
  })
}

export const useAddCollaborator = (repositoryId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { user_id: string; role: string }) =>
      api.post(`/api/sharing/repositories/${repositoryId}/collaborators`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: repositoryKey }),
  })
}

export const useCreateRelease = (repositoryId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: Record<string, any>) =>
      api.post(`/api/sharing/repositories/${repositoryId}/releases`, data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: repositoryKey })
      qc.invalidateQueries({ queryKey: ['sharing', 'timeline', repositoryId] })
    },
  })
}

export const useApproveRelease = (repositoryId: string | null) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: string; data: Record<string, any> }) =>
      api.post(`/api/sharing/releases/${vars.id}/approvals`, vars.data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: repositoryKey })
      if (repositoryId) {
        qc.invalidateQueries({ queryKey: ['sharing', 'timeline', repositoryId] })
      }
    },
  })
}

export const useRequestFederationGrant = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: {
      linkId: string
      organization: string
      permission_tier: string
      guardrail_scope?: Record<string, any>
    }) =>
      api.post(`/api/sharing/federation/links/${vars.linkId}/grants`, {
        organization: vars.organization,
        permission_tier: vars.permission_tier,
        guardrail_scope: vars.guardrail_scope ?? {},
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: repositoryKey }),
  })
}

export const useDecideFederationGrant = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: { id: string; decision: 'approve' | 'revoke'; notes?: string | null }) =>
      api.post(`/api/sharing/federation/grants/${vars.id}/decision`, {
        decision: vars.decision,
        notes: vars.notes ?? null,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: repositoryKey }),
  })
}

export const useCreateReleaseChannel = (repositoryId: string) => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: {
      name: string
      slug: string
      description?: string
      audience_scope?: 'internal' | 'partners' | 'public'
      guardrail_profile?: Record<string, any>
      federation_link_id?: string | null
    }) => api.post(`/api/sharing/repositories/${repositoryId}/channels`, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: repositoryKey }),
  })
}

export const usePublishReleaseChannelVersion = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (vars: {
      channelId: string
      release_id: string
      version_label: string
      guardrail_attestation?: Record<string, any>
      provenance_snapshot?: Record<string, any>
      mitigation_digest?: string | null
      grant_id?: string | null
    }) =>
      api.post(`/api/sharing/channels/${vars.channelId}/versions`, {
        release_id: vars.release_id,
        version_label: vars.version_label,
        guardrail_attestation: vars.guardrail_attestation ?? {},
        provenance_snapshot: vars.provenance_snapshot ?? {},
        mitigation_digest: vars.mitigation_digest ?? null,
        grant_id: vars.grant_id ?? null,
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: repositoryKey }),
  })
}

export const useRepositoryTimeline = (repositoryId: string | null) => {
  return useQuery({
    queryKey: ['sharing', 'timeline', repositoryId],
    queryFn: async () => {
      if (!repositoryId) {
        return [] as DNARepositoryTimelineEvent[]
      }
      const resp = await api.get(`/api/sharing/repositories/${repositoryId}/timeline`)
      return resp.data as DNARepositoryTimelineEvent[]
    },
    enabled: Boolean(repositoryId),
  })
}

type ReviewStreamEvent = {
  type: 'snapshot' | 'timeline'
  repository?: DNARepository
  release?: DNARepositoryRelease
  release_channel?: DNARepositoryReleaseChannel
  federation_link?: DNARepositoryFederationLink
  federation_grant?: DNARepositoryFederationGrant
  id?: string
  repository_id?: string
  release_id?: string | null
  event_type?: string
  payload?: Record<string, any>
  created_at?: string
  created_by_id?: string | null
}

type ReviewStreamOptions = {
  eventSourceFactory?: (url: string) => EventSource
}

export const useSharingReviewStream = (
  repositoryId: string | null,
  options?: ReviewStreamOptions,
) => {
  const queryClient = useQueryClient()
  const sourceRef = useRef<EventSource | null>(null)

  // purpose: subscribe to sharing SSE stream and hydrate repository/timeline caches
  // status: experimental
  useEffect(() => {
    if (!repositoryId) {
      return
    }

    const factory = options?.eventSourceFactory ?? ((url: string) => new EventSource(url))
    const source = factory(`/api/sharing/repositories/${repositoryId}/reviews/stream`)
    sourceRef.current = source

    source.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as ReviewStreamEvent
        if (payload.type === 'snapshot' && payload.repository) {
          queryClient.setQueryData<DNARepository[] | undefined>(repositoryKey, (existing) => {
            const others = (existing ?? []).filter((repo) => repo.id !== payload.repository!.id)
            return [...others, payload.repository!]
          })
          queryClient.setQueryData<DNARepositoryTimelineEvent[] | undefined>(
            ['sharing', 'timeline', repositoryId],
            (current) => current ?? [],
          )
          return
        }
        if (payload.type === 'timeline') {
          if (payload.release && repositoryId) {
            queryClient.setQueryData<DNARepository[] | undefined>(repositoryKey, (existing) => {
              if (!existing) return existing
              return existing.map((repo) => {
                if (repo.id !== repositoryId) return repo
                const releases = [payload.release!, ...repo.releases.filter((r) => r.id !== payload.release!.id)]
                return { ...repo, releases }
              })
            })
          }
          if (payload.federation_link && repositoryId) {
            queryClient.setQueryData<DNARepository[] | undefined>(repositoryKey, (existing) => {
              if (!existing) return existing
              return existing.map((repo) => {
                if (repo.id !== repositoryId) return repo
                const links = [
                  payload.federation_link!,
                  ...repo.federation_links.filter((link) => link.id !== payload.federation_link!.id),
                ]
                return { ...repo, federation_links: links }
              })
            })
          }
          if (payload.federation_grant && repositoryId) {
            queryClient.setQueryData<DNARepository[] | undefined>(repositoryKey, (existing) => {
              if (!existing) return existing
              return existing.map((repo) => {
                if (repo.id !== repositoryId) return repo
                return {
                  ...repo,
                  federation_links: repo.federation_links.map((link) => {
                    if (link.id !== payload.federation_grant!.link_id) return link
                    const grants = [
                      payload.federation_grant!,
                      ...link.grants.filter((grant) => grant.id !== payload.federation_grant!.id),
                    ]
                    return { ...link, grants }
                  }),
                }
              })
            })
          }
          if (payload.release_channel && repositoryId) {
            queryClient.setQueryData<DNARepository[] | undefined>(repositoryKey, (existing) => {
              if (!existing) return existing
              return existing.map((repo) => {
                if (repo.id !== repositoryId) return repo
                const channels = [
                  payload.release_channel!,
                  ...repo.release_channels.filter((channel) => channel.id !== payload.release_channel!.id),
                ]
                return { ...repo, release_channels: channels }
              })
            })
          }
          if (payload.id && repositoryId) {
            const timelineEvent: DNARepositoryTimelineEvent = {
              id: payload.id,
              repository_id: payload.repository_id ?? repositoryId,
              release_id: payload.release_id ?? null,
              event_type: payload.event_type ?? 'timeline.event',
              payload: payload.payload ?? {},
              created_at: payload.created_at ?? new Date().toISOString(),
              created_by_id: payload.created_by_id ?? null,
            }
            queryClient.setQueryData<DNARepositoryTimelineEvent[] | undefined>(
              ['sharing', 'timeline', repositoryId],
              (existing) => {
                const base = existing ?? []
                const filtered = base.filter((item) => item.id !== timelineEvent.id)
                return [timelineEvent, ...filtered]
              },
            )
          }
        }
      } catch (error) {
        console.error('Failed to parse sharing review stream event', error)
      }
    }

    source.onerror = () => {
      source.close()
      sourceRef.current = null
    }

    return () => {
      source.close()
      sourceRef.current = null
    }
  }, [repositoryId, options?.eventSourceFactory, queryClient])

  return { isConnected: Boolean(sourceRef.current), close: () => sourceRef.current?.close() }
}
