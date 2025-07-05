'use client'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import type { SequenceFeature, ChromatogramData, BlastResult, SequenceJob } from '../types'

export const useAnnotateSequence = () => {
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.append('format', 'genbank')
      form.append('upload', file)
      const resp = await api.post('/api/sequence/annotate', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return resp.data as SequenceFeature[]
    },
  })
}

export const useChromatogram = () => {
  return useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData()
      form.append('upload', file)
      const resp = await api.post('/api/sequence/chromatogram', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return resp.data as ChromatogramData
    },
  })
}

export const useBlastSearch = () => {
  return useMutation({
    mutationFn: async (payload: { query: string; subject: string }) => {
      const resp = await api.post('/api/sequence/blast', payload)
      return resp.data as BlastResult
    },
  })
}

export const useCreateSequenceJob = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (vars: { file: File; format: string }) => {
      const form = new FormData()
      form.append('format', vars.format)
      form.append('upload', vars.file)
      const resp = await api.post('/api/sequence/jobs', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return resp.data as SequenceJob
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['seqJobs'] }),
  })
}

export const useSequenceJobs = () => {
  return useQuery({
    queryKey: ['seqJobs'],
    queryFn: async () => {
      const resp = await api.get('/api/sequence/jobs')
      return resp.data as SequenceJob[]
    },
  })
}
