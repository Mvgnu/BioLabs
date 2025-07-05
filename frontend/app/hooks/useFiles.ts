'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import type { FileMeta, ChromatogramData, SequenceRead } from '../types'

export const useItemFiles = (itemId: string) => {
  return useQuery({
    queryKey: ['files', itemId],
    queryFn: async () => {
      const resp = await api.get(`/api/files/items/${itemId}`)
      return resp.data as FileMeta[]
    }
  })
}

export const useUploadFile = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (data: { itemId: string; file: File }) => {
      const form = new FormData()
      form.append('item_id', data.itemId)
      form.append('upload', data.file)
      return api.post('/api/files/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
    },
    onSuccess: (_resp, vars) => {
      qc.invalidateQueries({ queryKey: ['files', vars.itemId] })
    }
  })
}

export const useFileChromatogram = (fileId: string | null) => {
  return useQuery({
    queryKey: ['chromatogram', fileId],
    queryFn: async () => {
      const resp = await api.get(`/api/files/${fileId}/chromatogram`)
      return resp.data as ChromatogramData
    },
    enabled: !!fileId
  })
}

export const useFileSequence = (
  fileId: string | null,
  format?: string
) => {
  return useQuery({
    queryKey: ['fileSeq', fileId, format],
    queryFn: async () => {
      const resp = await api.get(`/api/files/${fileId}/sequence`, {
        params: format ? { format } : {},
      })
      return resp.data as SequenceRead[]
    },
    enabled: !!fileId,
  })
}
