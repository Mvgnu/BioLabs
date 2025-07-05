'use client'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import type { CalendarEvent } from '../types'

export const useCalendarEvents = () =>
  useQuery({
    queryKey: ['calendar'],
    queryFn: async () => {
      const res = await api.get('/api/calendar')
      return res.data as CalendarEvent[]
    },
  })

export const useCreateEvent = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (data: Partial<CalendarEvent>) => {
      const res = await api.post('/api/calendar', data)
      return res.data as CalendarEvent
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['calendar'] }),
  })
}

export const useUpdateEvent = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, data }: { id: string; data: Partial<CalendarEvent> }) => {
      const res = await api.put(`/api/calendar/${id}`, data)
      return res.data as CalendarEvent
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['calendar'] }),
  })
}

export const useDeleteEvent = () => {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/api/calendar/${id}`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['calendar'] }),
  })
}
